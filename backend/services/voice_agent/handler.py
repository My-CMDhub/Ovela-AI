"""
Voice Agent Handler Module.

Main handler class that bridges Twilio Media Streams to Deepgram Voice Agent API.
This is the primary orchestrator that uses all other modules:
- config.py: Settings and constants
- prompts.py: System prompts
- abuse_protection.py: Abuse detection and escalation
- silence_detection.py: Silence monitoring
- functions/: Function definitions and handlers
- bridges/: Twilio and Deepgram communication

Architecture:
    Twilio <─ Media Stream ─> VoiceAgentHandler <─ WebSocket ─> Deepgram Agent API
"""

import json
import logging
import asyncio
import base64
import time
import random
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import websockets
from twilio.rest import Client
from fastapi import WebSocket
from appwrite.id import ID

from core.config import settings
from services.appwrite import db_service
import os

# Import from sibling modules
from .config import (
    DEEPGRAM_AGENT_URL,
    ABUSE_CONFIG,
    get_random_greeting,
    get_random_farewell,
    get_random_silence_prompt,
)
from .prompts import get_system_prompt
from .demo_prompts import get_demo_prompt, get_demo_greeting, is_demo_mode
from .abuse_protection import AbuseProtection
from .silence_detection import SilenceMonitor
from .functions import get_booking_functions
from .functions.handlers import FunctionDispatcher, MOTEL_DB_ID
from .text_utils import prepare_for_tts, clean_tts_output

# TTS Provider config - set USE_ELEVENLABS=true in .env to test ElevenLabs
USE_ELEVENLABS = os.getenv("USE_ELEVENLABS", "false").lower() == "true"
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "cgSgspJ2msm6clMCkdW9")  # Jessica voice

logger = logging.getLogger(__name__)


class VoiceAgentHandler:
    """
    Bridges Twilio Media Stream to Deepgram Voice Agent API.
    
    This handler orchestrates the entire voice call:
    1. Receives audio from Twilio
    2. Forwards to Deepgram for STT + LLM + TTS
    3. Handles function calls (bookings, queries)
    4. Monitors for abuse and silence
    5. Sends audio back to Twilio
    
    Usage:
        handler = VoiceAgentHandler(twilio_websocket)
        await handler.start()
    """
    
    # Demo limits (can be moved to config if needed)
    MAX_DEMO_DURATION_SECONDS = 180  # 3 minutes
    MAX_EXCHANGES = 12
    
    def __init__(self, websocket: WebSocket):
        """
        Initialize the voice agent handler.
        
        Args:
            websocket: FastAPI WebSocket connection from Twilio
        """
        # WebSocket connections
        self.twilio_ws = websocket
        self.deepgram_ws = None
        self.stream_sid = None
        
        # User info (populated from Twilio custom parameters)
        self.user_name = "there"
        self.business_name = "your business"
        self.user_phone = "unknown"
        self.custom_params = {}  # Store all custom params for later access
        
        # State tracking
        self.is_running = True
        self.call_start_time = None
        self.call_sid = None
        self.exchange_count = 0
        self.booking_completed = False
        
        # Transfer state tracking
        self._transfer_pending = False
        self._transfer_tts_done = asyncio.Event()
        self._transfer_target = None
        
        # Latency tracking (for debugging/analytics)
        self.user_speech_start_time = None
        self.ai_response_start_time = None
        
        # Modular components
        self.silence_monitor = SilenceMonitor()
        self.abuse_protection = AbuseProtection()
        self.function_dispatcher = None  # Initialized after getting user_phone
        
        # Background tasks
        self.duration_monitor_task = None
        
        # Transcript for analytics
        self.transcript = []
        self.call_outcome = "completed"
        
        # Environment detection (demo vs production call)
        self.is_demo_call = False  # Set in _handle_twilio_start based on custom parameters
        
        # Multi-tenant support
        # Demo calls → "ovela_demo", Production calls → resolved from phone or default "lydoun"
        self.tenant_id = "ovela_demo"  # Default to demo, updated in _handle_twilio_start
    
    # =========================================================================
    # DEEPGRAM SETTINGS
    # =========================================================================
    
    def _get_settings_message(self) -> dict:
        """
        Build the Deepgram Voice Agent Settings message.
        
        This configures:
        - Audio encoding (mulaw for Twilio)
        - STT model (flux-general-en)
        - LLM (OpenAI gpt-4o-mini)
        - TTS (Deepgram aura-2-thalia-en)
        - System prompt and functions
        """
        # Check for transfer failure (from failover loop)
        transfer_failed = self.custom_params.get("transfer_failed") == "true"
        
        # Add welcome message to start conversation (unless we have context)
        # Deepgram's "speak" -> "greeting" handles the audio, but we also want
        # to seed the conversation history if we're resuming
        system_context = ""
        if transfer_failed:
             # System message to inform AI of context (hidden from user)
            system_context = "System: The user has returned because the staff transfer failed (no answer). Apologize and ask how you can help."
            logger.info("⚠️ Resuming session after failed transfer")
            
            # Send hidden context message to AI
            msg = {
                "type": "ConversationText",
                "role": "user",  # Simulate user or system prompt
                "content": system_context
            }
            # We can't send this immediately as DG might not be ready, 
            # but providing it on first valid interaction helps.
            # Actually, better to inject it as the first "user" message logic
            # or rely on the fact the user says "Hello?"
            
            # Better approach: Append to history immediately so model sees it
            # self.conversation_history.append({"role": "system", "content": system_context})
            
        return {
            "type": "Settings",
            "audio": {
                "input": {
                    "encoding": "mulaw",
                    "sample_rate": 8000
                },
                "output": {
                    "encoding": "mulaw",
                    "sample_rate": 8000,
                    "container": "none"
                }
            },
            "agent": {
                "language": "en",
                "listen": {
                    "provider": {
                        "type": "deepgram",
                        "model": "flux-general-en"
                    }
                },
                "think": {
                    "provider": {
                        "type": "open_ai",
                        "model": "gpt-4o-mini",
                        "temperature": 0.85
                    },
                    "prompt": self._get_active_prompt() + ("\n\n[CONTEXT: " + system_context + "]" if system_context else ""),
                    "functions": get_booking_functions()
                },
                "speak": self._get_tts_config(),
                "greeting": "Sorry about that, it looks like no one is available. How can I help you instead?" if transfer_failed else self._get_active_greeting()
            }
        }
    
    def _get_active_prompt(self) -> str:
        """Get the active prompt - demo prompt if configured, otherwise motel."""
        demo_prompt = get_demo_prompt(
            current_date=datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%A, %d %B %Y"),
            current_time=datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%I:%M %p")
        )
        if demo_prompt:
            logger.info(f"Using DEMO prompt mode")
            return demo_prompt
        return get_system_prompt(
            current_date=datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%A, %d %B %Y"),
            current_time=datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%I:%M %p")
        )
    
    def _get_active_greeting(self) -> str:
        """Get the active greeting - demo greeting if configured, otherwise motel."""
        if is_demo_mode():
            return get_demo_greeting()
        return get_random_greeting()
    
    def _get_tts_config(self) -> dict:
        """
        Get TTS configuration.
        Set USE_ELEVENLABS=true in .env to test ElevenLabs.
        
        Deepgram Voice Agent API spec for ElevenLabs:
        - URL must use wss:// with stream-input endpoint
        - Only xi-api-key header is required
        """
        if USE_ELEVENLABS:
            elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
            logger.info(f"🎤 Using ElevenLabs TTS (voice: {ELEVENLABS_VOICE_ID})")
            return {
                "provider": {
                    "type": "eleven_labs",
                    "model_id": "eleven_turbo_v2_5",
                    "language_code": "en-US"
                },
                "endpoint": {
                    "url": f"wss://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream-input",
                    "headers": {
                        "xi-api-key": elevenlabs_api_key
                    }
                }
            }
        else:
            logger.info(f"🎤 Using Deepgram TTS (model: aura-2-thalia-en)")
            return {
                "provider": {
                    "type": "deepgram",
                    "model": "aura-2-thalia-en"
                }
            }
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    
    async def start(self):
        """
        Main loop - bridges Twilio and Deepgram.
        
        Listens for Twilio WebSocket messages and routes them appropriately:
        - start: Initialize Deepgram connection
        - media: Forward audio to Deepgram
        - stop: Clean up and end
        """
        logger.info("🚀 VoiceAgentHandler starting")
        
        try:
            async for message in self.twilio_ws.iter_text():
                if not self.is_running:
                    break
                
                data = json.loads(message)
                event_type = data.get("event")
                
                if event_type == "start":
                    await self._handle_twilio_start(data)
                elif event_type == "media":
                    await self._handle_twilio_media(data)
                elif event_type == "stop":
                    logger.info("📴 Twilio stream stopped")
                    self.is_running = False
                    break
                    
        except Exception as e:
            logger.error(f"VoiceAgentHandler error: {e}", exc_info=True)
        finally:
            await self._cleanup()
    
    # =========================================================================
    # TWILIO EVENT HANDLERS
    # =========================================================================
    
    async def _handle_twilio_start(self, data: dict):
        """
        Handle Twilio stream start event.
        
        Extracts call metadata and connects to Deepgram Agent API.
        """
        self.stream_sid = data["start"]["streamSid"]
        
        # Extract Call SID for hangup capability
        if "start" in data and "callSid" in data["start"]:
            self.call_sid = data["start"]["callSid"]
        
        # Extract custom parameters from Twilio
        custom_params = data["start"].get("customParameters", {})
        self.custom_params = custom_params  # Store for later access (e.g., transfer_failed flag)
        self.user_name = custom_params.get("user_name", "there")
        self.business_name = custom_params.get("business_name", "your business")
        self.user_phone = custom_params.get("user_phone", "unknown")
        
        # Multi-tenant detection
        self.tenant_id = custom_params.get("tenant_id", "lydoun")
        self.is_demo_call = custom_params.get("is_demo", "false").lower() == "true"
        call_type = "DEMO" if self.is_demo_call else "PRODUCTION"
        
        # Multi-tenant: Resolve tenant_id based on call type
        # Demo calls → "ovela_demo" (Ovela website demos)
        # Production calls → "lydoun" for now (future: resolve from Twilio To number)
        if self.is_demo_call:
            self.tenant_id = "ovela_demo"
        else:
            # TODO: When adding 2nd tenant, resolve from db_service.get_tenant_by_phone(to_phone)
            self.tenant_id = "lydoun"
        
        logger.info(f"🟢 Twilio stream started: {self.stream_sid} for {self.user_name} [{call_type}] tenant={self.tenant_id}")
        
        # Initialize timing
        self.call_start_time = time.time()
        self.abuse_protection.set_call_start_time(self.call_start_time)
        
        # Initialize function dispatcher with user context
        self.function_dispatcher = FunctionDispatcher(
            db_service=db_service,
            user_phone=self.user_phone,
            save_reservation_fn=self._save_motel_reservation,
            abuse_protection=self.abuse_protection,
            tenant_id=self.tenant_id  # Pass tenant_id to function dispatcher
        )
        
        # Connect to Deepgram Voice Agent API
        try:
            self.deepgram_ws = await websockets.connect(
                DEEPGRAM_AGENT_URL,
                subprotocols=["token", settings.DEEPGRAM_API_KEY],
                ping_interval=5,
                ping_timeout=20
            )
            
            logger.info("🟢 Connected to Deepgram Voice Agent API")
            
            # Send Settings message
            settings_msg = self._get_settings_message()
            await self.deepgram_ws.send(json.dumps(settings_msg))
            logger.info("📤 Sent Settings to Deepgram Agent")
            
            # Log TTS provider clearly
            tts_provider = settings_msg["agent"]["speak"]["provider"]["type"]
            if tts_provider == "eleven_labs":
                logger.info(f"🎤 TTS PROVIDER: ElevenLabs (voice: {ELEVENLABS_VOICE_ID})")
            else:
                model = settings_msg["agent"]["speak"]["provider"]["model"]
                logger.info(f"🎤 TTS PROVIDER: Deepgram (model: {model})")
            
            # Start background tasks
            asyncio.create_task(self._receive_from_deepgram())
            self.duration_monitor_task = asyncio.create_task(self._monitor_call_duration())
            
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram Agent: {e}")
            raise
    
    async def _handle_twilio_media(self, data: dict):
        """Forward Twilio audio to Deepgram Agent."""
        if not self.deepgram_ws:
            return
        
        try:
            # Twilio sends base64-encoded mulaw audio
            payload = data["media"]["payload"]
            audio_bytes = base64.b64decode(payload)
            
            # Forward raw audio to Deepgram
            await self.deepgram_ws.send(audio_bytes)
            
        except Exception as e:
            logger.warning(f"Error forwarding audio to Deepgram: {e}")
    
    # =========================================================================
    # DEEPGRAM EVENT HANDLERS
    # =========================================================================
    
    async def _receive_from_deepgram(self):
        """
        Receive audio/events from Deepgram Agent and process them.
        
        Routes:
        - Binary data → Forward audio to Twilio
        - JSON events → Handle based on type
        """
        logger.info("🎧 Started receiving from Deepgram Agent")
        
        try:
            async for message in self.deepgram_ws:
                if not self.is_running:
                    break
                
                if isinstance(message, bytes):
                    # Audio from TTS - forward to Twilio
                    await self._send_audio_to_twilio(message)
                else:
                    # JSON event
                    await self._handle_deepgram_event(json.loads(message))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 Deepgram connection closed")
        except Exception as e:
            logger.error(f"Error receiving from Deepgram: {e}")
    
    async def _send_audio_to_twilio(self, audio_bytes: bytes):
        """Send audio to Twilio Media Stream."""
        try:
            payload = base64.b64encode(audio_bytes).decode("utf-8")
            
            media_message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload": payload
                }
            }
            
            await self.twilio_ws.send_json(media_message)
            
        except Exception as e:
            logger.warning(f"Error sending audio to Twilio: {e}")
    
    async def _handle_deepgram_event(self, event: dict):
        """
        Handle JSON events from Deepgram Agent.
        
        Event types:
        - Welcome: Connection established
        - SettingsApplied: Configuration confirmed
        - ConversationText: Transcript of speech
        - UserStartedSpeaking: VAD detected user voice
        - AgentStartedSpeaking: AI started response
        - AgentAudioDone: AI finished speaking
        - FunctionCallRequest: AI wants to call a function
        - Error/Close: Connection issues
        """
        event_type = event.get("type")
        
        # DEBUG: Log ALL events to understand what Deepgram sends
        # This helps diagnose silence detection issues
        ai_speaking = getattr(self, '_ai_is_speaking', False)
        logger.info(f"📨 DG_EVENT: {event_type} | ai_speaking={ai_speaking} | full={event}")
        
        if event_type == "Welcome":
            logger.info(f"🤝 Deepgram Agent welcome: {event}")
            
        elif event_type == "SettingsApplied":
            logger.info("⚙️ Deepgram Agent settings applied")
            
        elif event_type == "ConversationText":
            await self._handle_conversation_text(event)
            
        elif event_type == "UserStartedSpeaking":
            await self._handle_user_started_speaking()
            
        elif event_type == "AgentStartedSpeaking":
            await self._handle_agent_started_speaking()
            
        elif event_type == "AgentAudioDone":
            await self._handle_agent_audio_done()
            
        elif event_type == "FunctionCallRequest":
            await self._handle_function_call(event)
            
        elif event_type == "Error":
            logger.error(f"❌ Deepgram Agent error: {event}")
            
        elif event_type == "Close":
            logger.info("👋 Deepgram Agent closing")
            self.is_running = False
            
        else:
            logger.debug(f"Deepgram event: {event_type}")
    
    async def _handle_conversation_text(self, event: dict):
        """Handle transcribed conversation text from Deepgram."""
        role = event.get("role", "")
        content = event.get("content", "")
        
        if role == "user":
            # Log with latency info
            if self.user_speech_start_time:
                latency_ms = int((time.time() - self.user_speech_start_time) * 1000)
                logger.info(f"[User]: {content} (STT latency: {latency_ms}ms)")
            else:
                logger.info(f"[User]: {content}")
            
            # Track exchange
            self.exchange_count += 1
            self.transcript.append({
                "role": "user",
                "text": content,
                "timestamp": time.strftime("%H:%M:%S")
            })
            
            # Mark timing for response latency
            self.ai_response_start_time = time.time()
            
            # Check for spam/abuse
            spam_result = self.abuse_protection.check_spam_behavior(content)
            if spam_result.get("is_spam"):
                if spam_result.get("should_hangup"):
                    self.call_outcome = "spam_terminated"
                    await self._hangup_with_farewell(spam_result.get("message", "Take care!"))
                    return
                elif spam_result.get("warning"):
                    await self._inject_message(spam_result["warning"])
                    
        elif role == "assistant":
            # Extract control signals and clean content for logging/transcript
            clean_content, signals = prepare_for_tts(content)
            
            # STATE MACHINE: AI is now speaking
            # This replaces AgentStartedSpeaking which Deepgram doesn't send
            self._ai_is_speaking = True
            
            # During escalation, preserve check ID so hard/abandon checks stay valid
            in_escalation = getattr(self, '_in_silence_escalation', False)
            self.silence_monitor.on_ai_started_speaking(preserve_check_id=in_escalation)
            
            # Don't reset escalation flag - let the escalation sequence continue
            
            # Log clean content with latency info
            if self.ai_response_start_time:
                latency_ms = int((time.time() - self.ai_response_start_time) * 1000)
                logger.info(f"[AI]: {clean_content} (Response latency: {latency_ms}ms)")
            else:
                logger.info(f"[AI]: {clean_content}")
            
            # Save clean content to transcript (not raw with signals)
            self.last_ai_message = clean_content
            self.transcript.append({
                "role": "ai",
                "text": clean_content,
                "timestamp": time.strftime("%H:%M:%S")
            })
            
            # Handle control signals that were extracted
            if "[[HANGUP]]" in signals:
                logger.info("📞 AI initiated hangup (Signal detected)")
                await self._hangup_call()
    
    async def _handle_user_started_speaking(self):
        """Handle VAD detection of user speech."""
        logger.info("🎤 User started speaking (VAD)")
        
        # Track timing
        self.user_speech_start_time = time.time()
        
        # User spoke - exit any silence escalation cycle
        self._in_silence_escalation = False
        
        # Notify silence monitor
        self.silence_monitor.on_user_speech()
        
        # Send clear event to Twilio to stop agent audio immediately
        clear_message = {
            "event": "clear",
            "streamSid": self.stream_sid
        }
        await self.twilio_ws.send_json(clear_message)
    
    async def _handle_agent_started_speaking(self):
        """
        Handle agent starting to speak - invalidate pending silence checks.
        
        This is critical for proper silence detection:
        - When AI starts responding, any pending silence checks from previous
          utterances must be invalidated
        - This prevents "silence while AI is speaking" false positives
        """
        logger.info("🔊 Agent started speaking")
        
        # Set AI speaking state
        self._ai_is_speaking = True
        
        # Invalidate any pending silence checks by incrementing the check ID
        self.silence_monitor.on_ai_started_speaking()
        
        # Cancel any silence escalation - AI is responding
        self._in_silence_escalation = False
    
    async def _handle_agent_audio_done(self):
        """
        Handle agent finished speaking - start silence monitoring.
        
        STATE MACHINE: AgentAudioDone means Deepgram finished sending audio.
        We now switch to "awaiting user utterance" state.
        """
        logger.info("🔇 Agent audio done")
        
        # Mark AI as not speaking - transition to awaiting user
        self._ai_is_speaking = False
        
        # If we're waiting for transfer TTS to complete, signal it's done
        if self._transfer_pending:
            logger.info("✅ Transfer TTS playback completed")
            self._transfer_tts_done.set()
            return  # Don't start silence monitoring during transfer
        
        # If we're in a silence escalation cycle, don't start a new cycle
        if getattr(self, '_in_silence_escalation', False):
            logger.debug("⏱️ Skipping new silence cycle - in escalation mode")
            return
        
        # Short grace period to allow for streaming chunks
        await asyncio.sleep(0.3)  # 300ms grace period
        
        # Check if AI started speaking again (new ConversationText came in)
        if getattr(self, '_ai_is_speaking', False):
            logger.debug("⏱️ Skipping silence check - AI speaking again")
            return
        
        # Start silence monitoring - no TTS buffer, trust event timing
        self.silence_monitor.on_ai_finished_speaking()
        check_id = self.silence_monitor.get_check_id()
        
        # Schedule silence check
        logger.info(f"⏱️ Scheduling silence check #{check_id} (soft={self.silence_monitor.get_soft_threshold()}s)")
        asyncio.create_task(self._check_silence(check_id))
    
    async def _handle_function_call(self, event: dict):
        """Handle function call request from Deepgram Agent."""
        functions = event.get("functions", [])
        
        if not functions:
            logger.error(f"❌ FunctionCallRequest has no functions. Event: {event}")
            return
        
        # Get first function from array
        func_data = functions[0]
        function_name = func_data.get("name", "")
        call_id = func_data.get("id", "")
        arguments_str = func_data.get("arguments", "{}")
        
        # Parse arguments
        try:
            function_args = json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse function arguments: {e}")
            function_args = {}
        
        if not function_name or not call_id:
            logger.error(f"❌ FunctionCallRequest missing name or id. Event: {event}")
            return
        
        logger.info(f"🔧 Function call: {function_name}({function_args})")
        
        # Inject acknowledgment for slow/database tools to avoid silence
        SLOW_TOOLS = [
            "report_missing_booking", 
            "create_booking", 
            "request_human_callback",
            "lookup_booking"
        ]
        if function_name in SLOW_TOOLS:
            await self._inject_message("Got it, just one moment...")
        
        # Execute via dispatcher
        result = await self.function_dispatcher.execute(function_name, function_args)
        
        # Check for transfer signal
        if result.get("action") == "transfer":
            transfer_to = result.get("transfer_to")
            transfer_message = result.get("message", "Transferring you now...")
            
            logger.info(f"📞 Transfer requested to {transfer_to}")
            logger.info(f"📢 Playing transfer message: '{transfer_message}'")
            
            # Set transfer pending flag and reset the event
            self._transfer_pending = True
            self._transfer_tts_done.clear()
            self._transfer_target = transfer_to
            
            # Inject the transfer message
            await self._inject_message(transfer_message)
            
            # Wait for TTS to actually complete (AgentAudioDone event)
            # with a timeout as safety fallback
            logger.info("⏳ Waiting for TTS playback to complete...")
            try:
                await asyncio.wait_for(self._transfer_tts_done.wait(), timeout=20.0)
                logger.info("✅ TTS confirmed complete, executing transfer")
            except asyncio.TimeoutError:
                logger.warning("⚠️ TTS completion timeout, proceeding with transfer anyway")
            
            await self._execute_twilio_transfer(transfer_to)
            return  # Don't send function response, call is being transferred
        
        # Check for hangup signal from flag_off_topic
        if result.get("should_hangup"):
            logger.info(f"🚫 Flag off-topic limit reached - hanging up")
            self.call_outcome = "abuse_timeout"
            asyncio.create_task(self._hangup_with_farewell(
                result.get("farewell", "Thanks for calling! Take care!")
            ))
        
        # Check if booking was completed
        if function_name == "create_booking" and result.get("success"):
            self.booking_completed = True
        
        # Send response back to Deepgram
        await self._send_function_response(call_id, function_name, result)
    
    async def _send_function_response(self, call_id: str, function_name: str, result: dict):
        """Send function result back to Deepgram (V1 API format)."""
        if not self.deepgram_ws:
            return
        
        try:
            response = {
                "type": "FunctionCallResponse",
                "id": call_id,
                "name": function_name,
                "content": json.dumps(result)
            }
            await self.deepgram_ws.send(json.dumps(response))
            logger.info(f"📤 Sent function response for {function_name}")
        except Exception as e:
            logger.error(f"Failed to send function response: {e}")
    
    # =========================================================================
    # SILENCE DETECTION
    # =========================================================================
    
    async def _check_silence(self, check_id: int):
        """Check for soft silence threshold."""
        # STRICT GUARD: Never run silence check while AI is speaking or hanging up
        if getattr(self, '_ai_is_speaking', False):
            logger.info(f"⏹️ Silence check #{check_id} cancelled - AI is speaking")
            return
        if getattr(self, '_is_hanging_up', False):
            logger.info(f"⏹️ Silence check #{check_id} cancelled - call hanging up")
            return
        
        threshold = self.silence_monitor.get_soft_threshold()
        logger.info(f"⏱️ Silence check #{check_id} waiting {threshold}s")
        await asyncio.sleep(threshold)
        
        if not self.is_running:
            logger.debug(f"⏱️ Silence check #{check_id} cancelled: call ended")
            return
        
        # Check again if AI started speaking during wait
        if getattr(self, '_ai_is_speaking', False):
            logger.info(f"⏹️ Silence check #{check_id} cancelled - AI started speaking")
            return
        
        result = self.silence_monitor.check_silence(check_id)
        action = result.get("action")
        reason = result.get("reason", "")
        
        logger.info(f"⏱️ Silence check #{check_id} result: action={action}, reason={reason}")
        
        if action == "soft_prompt":
            logger.info(f"⏱️ Soft silence - gentle check-in")
            self._in_silence_escalation = True  # Prevent new silence cycles during escalation
            await self._inject_message(result.get("prompt", get_random_silence_prompt()))
            # Continue escalation chain with same check_id
            asyncio.create_task(self._check_hard_silence(check_id))
            
        elif action == "abandon":
            self.call_outcome = "timeout_silence"
            await self._inject_farewell_and_hangup()
    
    async def _check_hard_silence(self, check_id: int):
        """Check for hard silence threshold (second follow-up)."""
        # Guard: Exit if AI started speaking
        if getattr(self, '_ai_is_speaking', False):
            self._in_silence_escalation = False
            return
        
        # Wait delta between soft and hard threshold
        hard_wait = self.silence_monitor.get_hard_threshold() - self.silence_monitor.get_soft_threshold()
        logger.info(f"⏱️ Hard silence check waiting {hard_wait}s")
        await asyncio.sleep(hard_wait)
        
        if not self.is_running or getattr(self, '_ai_is_speaking', False):
            self._in_silence_escalation = False
            return
        
        result = self.silence_monitor.check_silence(check_id)
        action = result.get("action")
        
        if action == "hard_prompt":
            logger.info(f"⏱️ Hard silence - urgent check-in")
            await self._inject_message(result.get("prompt", "Hello? Still there?"))
            asyncio.create_task(self._check_abandon_silence(check_id))
            
        elif action == "abandon":
            self._in_silence_escalation = False
            self.call_outcome = "timeout_silence"
            await self._inject_farewell_and_hangup()
        else:
            # User spoke or check invalidated - exit escalation
            self._in_silence_escalation = False
    
    async def _check_abandon_silence(self, check_id: int):
        """Check for abandon threshold - end call if still silent."""
        # Guard: Exit if AI started speaking
        if getattr(self, '_ai_is_speaking', False):
            self._in_silence_escalation = False
            return
        
        abandon_wait = self.silence_monitor.get_abandon_threshold() - self.silence_monitor.get_hard_threshold()
        logger.info(f"⏱️ Abandon silence check waiting {abandon_wait}s")
        await asyncio.sleep(abandon_wait)
        
        if not self.is_running or getattr(self, '_ai_is_speaking', False):
            self._in_silence_escalation = False
            return
        
        result = self.silence_monitor.check_silence(check_id)
        
        if result.get("action") == "abandon":
            logger.info(f"⏱️ Extended silence ({int(result.get('duration', 0))}s) - ending call")
            self._in_silence_escalation = False
            self.call_outcome = "timeout_silence"
            await self._inject_farewell_and_hangup()
        else:
            # User spoke or check invalidated
            self._in_silence_escalation = False
    
    # =========================================================================
    # DURATION MONITORING
    # =========================================================================
    
    async def _monitor_call_duration(self):
        """
        Background task that monitors call duration and enforces time caps.
        
        Uses thresholds from ABUSE_CONFIG:
        - soft_warning_minutes: Inject gentle "wrapping up" prompt
        - hard_cap_minutes: Force end call or transfer to staff
        
        Behavior differs based on call type:
        - Demo calls: Polite hangup when cap reached
        - Production calls: Transfer to staff when cap reached
        """
        call_type = "DEMO" if self.is_demo_call else "PRODUCTION"
        logger.info(
            f"⏱️ Duration monitor started [{call_type}]: "
            f"soft={ABUSE_CONFIG['soft_warning_minutes']}min, hard={ABUSE_CONFIG['hard_cap_minutes']}min"
        )
        
        while self.is_running:
            await asyncio.sleep(10)
            
            if not self.is_running or not self.call_start_time:
                break
            
            # Check duration using abuse protection
            duration_result = self.abuse_protection.check_duration()
            action = duration_result.get("action")
            
            if action == "soft_warning":
                logger.info(f"⏱️ Soft time warning [{call_type}]")
                await self._inject_message(duration_result.get("message", "We've been chatting for a while..."))
                
            elif action == "hard_cap":
                self.call_outcome = duration_result.get("outcome", "timeout_duration")
                
                # Check if we should transfer instead of hanging up
                # Production calls get transferred; Demo calls get polite hangup
                should_transfer = ABUSE_CONFIG.get("transfer_on_cap", False) and not self.is_demo_call
                
                if should_transfer:
                    logger.info(f"🚨 Duration cap reached - transferring to staff [{call_type}]")
                    transfer_message = (
                        "I've been helping you for a while now. "
                        "Let me connect you with our team who can assist you further."
                    )
                    await self._inject_message(transfer_message)
                    
                    # Wait for TTS to play before transfer
                    await asyncio.sleep(6)
                    
                    # Attempt transfer - if it fails or staff doesn't answer,
                    # the transfer-status callback will return caller to AI
                    await self._execute_twilio_transfer(settings.STAFF_PHONE_NUMBER)
                else:
                    # Demo mode or transfer_on_cap disabled: polite hangup
                    logger.info(f"🚫 Hard time cap reached - ending call [{call_type}]")
                    await self._hangup_with_farewell(duration_result.get("farewell", "Thanks for calling!"))
                
                break
    
    # =========================================================================
    # MESSAGING & CALL CONTROL
    # =========================================================================
    
    async def _inject_message(self, content: str):
        """Inject a message for the agent to speak."""
        if not self.deepgram_ws:
            return
        
        try:
            inject_message = {
                "type": "InjectAgentMessage",
                "content": content
            }
            await self.deepgram_ws.send(json.dumps(inject_message))
            logger.info(f"📨 Injected: '{content[:50]}...'")
        except Exception as e:
            logger.warning(f"Failed to inject message: {e}")
    
    async def _hangup_call(self):
        """Terminate the Twilio call gracefully."""
        if not self.call_sid:
            logger.warning("Cannot hangup: No Call SID")
            return
        
        logger.info(f"📵 Hanging up call: {self.call_sid}")
        
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.calls(self.call_sid).update(status="completed")
            logger.info("✅ Call terminated successfully")
            self.is_running = False
        except Exception as e:
            logger.error(f"Failed to hangup call: {e}")
    
    async def _inject_farewell_and_hangup(self):
        """Inject farewell message before hanging up due to silence."""
        # Set flag to stop silence detection during hangup
        self._is_hanging_up = True
        if not self.deepgram_ws:
            await self._hangup_call()
            return
        
        try:
            farewell_messages = [
                "I can't seem to hear you anymore. Feel free to call back if you need help. Take care!",
                "It seems like we've lost connection. Please call us back anytime. Goodbye!",
                "I haven't heard from you in a while. Please call back if you need assistance. Have a great day!",
            ]
            
            farewell = random.choice(farewell_messages)
            await self._inject_message(farewell)
            
            # Wait for farewell to be spoken
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.warning(f"Failed to inject farewell: {e}")
        
        await self._hangup_call()
    
    async def _hangup_with_farewell(self, farewell_message: str):
        """Send a farewell message then hangup after delay."""
        # Set flag to stop silence detection during hangup
        self._is_hanging_up = True
        
        if not self.deepgram_ws:
            await self._hangup_call()
            return
        
        try:
            await self._inject_message(farewell_message)
            # Wait for TTS to complete - estimate based on message length
            # ~12 chars/sec for TTS, plus latency buffer
            estimated_tts_time = max(6, len(farewell_message) // 10)
            logger.info(f"⏳ Waiting {estimated_tts_time}s for farewell TTS")
            await asyncio.sleep(estimated_tts_time)
        except Exception as e:
            logger.warning(f"Failed to send farewell: {e}")
        
        await self._hangup_call()
    
    async def _execute_twilio_transfer(self, transfer_to: str):
        """
        Execute Twilio call transfer using TwiML update.
        
        Uses <Dial> to connect caller to staff phone.
        Falls back to AI if no answer within TRANSFER_TIMEOUT.
        """
        if not self.call_sid:
            logger.warning("Cannot transfer: No Call SID")
            await self._inject_message("I'm sorry, I couldn't complete the transfer. Let me take a message instead.")
            return
        
        logger.info(f"📞 Executing transfer to {transfer_to}")
        
        try:
            from twilio.twiml.voice_response import VoiceResponse, Dial
            
            # Build TwiML for transfer
            twiml = VoiceResponse()
            
            # Dial staff with timeout
            dial = Dial(
                timeout=settings.TRANSFER_TIMEOUT,
                caller_id=settings.TWILIO_PHONE_NUMBER,
                action=f"{settings.BACKEND_URL}/twilio/transfer-status"
            )
            dial.number(transfer_to)
            twiml.append(dial)
            
            # Fallback message if no answer (action callback handles this)
            twiml.say("Our staff are currently unavailable. Let me see how else I can help you.")
            twiml.redirect(f"{settings.BACKEND_URL}/twilio/voice")  # Return to AI
            
            # Update the live call with new TwiML
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.calls(self.call_sid).update(twiml=str(twiml))
            
            logger.info(f"✅ Call transfer initiated to {transfer_to}")
            self.call_outcome = "transferred"
            self.is_running = False  # Stop AI processing during transfer
            
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            await self._inject_message("I'm sorry, I couldn't complete the transfer. Let me take a message instead.")

    
    # =========================================================================
    # DATABASE & CLEANUP
    # =========================================================================
    
    def _save_motel_reservation(self, data: dict) -> dict:
        """Save reservation to motel_reservations collection."""
        try:
            doc_id = ID.unique()
            
            headers = {
                "Content-Type": "application/json",
                "X-Appwrite-Project": settings.APPWRITE_PROJECT_ID,
                "X-Appwrite-Key": settings.APPWRITE_API_KEY
            }
            
            # Add tenant_id to reservation data
            data["tenant_id"] = self.tenant_id
            
            url = f"{settings.APPWRITE_ENDPOINT}/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
            payload = {
                "documentId": doc_id,
                "data": data
            }
            
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.warning(f"Reservation save failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error saving reservation: {e}")
            return None
    
    async def _cleanup(self):
        """Clean up connections and save transcript."""
        logger.info("🧹 Cleaning up VoiceAgentHandler")
        self.is_running = False
        
        # Close Deepgram connection
        if self.deepgram_ws:
            try:
                await self.deepgram_ws.close()
            except Exception as e:
                logger.warning(f"Error closing Deepgram: {e}")
        
        # Save transcript
        try:
            duration = int(time.time() - self.call_start_time) if self.call_start_time else 0
            
            if self.transcript:
                db_service.create_demo_transcript(
                    phone=self.user_phone,
                    transcript=self.transcript,
                    exchange_count=self.exchange_count,
                    duration_seconds=duration,
                    outcome=self.call_outcome,
                    tenant_id=self.tenant_id  # Multi-tenant support
                )
                logger.info(f"📝 Saved transcript: {len(self.transcript)} entries, {duration}s")
        except Exception as e:
            logger.error(f"Error saving transcript: {e}")
        
        # Close Twilio WebSocket
        try:
            await self.twilio_ws.close()
        except Exception as e:
            logger.warning(f"Error closing Twilio WS: {e}")


# Backwards compatibility alias
DeepgramAgentHandler = VoiceAgentHandler
