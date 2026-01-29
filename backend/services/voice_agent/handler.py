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
import httpx
import websockets
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
    get_random_filler_prompt,
)
from .prompts import get_system_prompt
from .abuse_protection import AbuseProtection
from .silence_detection import SilenceMonitor
from .functions import get_booking_functions, get_saranda_functions, SarandaFunctionDispatcher, get_coalcreek_functions
from .functions.handlers import FunctionDispatcher, MOTEL_DB_ID
from .text_utils import prepare_for_tts, clean_tts_output
from services.motel_knowledge_base import set_tenant_context

CARTESIA_VOICE_ID = "f786b574-daa5-4673-aa0c-cbe3e8534c02"

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
        
        # Smart Greeting State
        self.has_user_spoken = False
        self.smart_greeting_task = None
        
        # Function tracking
        self._is_processing_function = False
        
        # Transfer state tracking
        self._transfer_pending = False
        self._transfer_tts_done = asyncio.Event()
        self._transfer_target = None
        
        # Latency tracking (for debugging/analytics)
        self.user_speech_start_time = None
        self.ai_response_start_time = None
        
        # Modular components
        self.silence_monitor = SilenceMonitor()
        self.abuse_protection = None  # Initialized after tenant_id is determined
        self.function_dispatcher = None  # Initialized after getting user_phone
        
        # Background tasks
        self.duration_monitor_task = None
        
        # Transcript for analytics
        self.transcript = []
        self.call_outcome = "completed"
        
        # Environment detection (demo vs production call)
        self.is_demo_call = False  # Set in _handle_twilio_start based on custom parameters
        
        # Multi-tenant support
        self.tenant_id = "coalcreek"  # Default to coalcreek
        self.demo_type = None
        
        # Smart Memory (for latency optimization & amnesia fix)
        self.memory = {
            "name": None,
            "order_summary": None,
            "pickup_time": None
        }
        
        # Tenant Configuration (Database Driven)
        self.tenant_config = {}
    
    # =========================================================================
    # DEEPGRAM SETTINGS
    # =========================================================================
    
    def _get_settings_message(self) -> dict:
        """
        Build the Deepgram Voice Agent Settings message.
        
        This configures:
        - Audio encoding (mulaw for Twilio)
        - STT model (flux-general-en)
        - LLM (OpenAI gpt-4.1-mini)
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
            
        # Extract voice settings from DB config
        voice_settings = self.tenant_config.get("voice_settings", {})
        
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
                        "model": voice_settings.get("model", "nova-3"),
                        "endpointing": voice_settings.get("endpointing", 350),  
                        "smart_format": True
                    }
                },
                "think": self._get_llm_config(),
                "speak": self._get_tts_config(),
                "greeting": "Sorry about that, it looks like no one is available. How can I help you instead?" if transfer_failed else self._get_active_greeting()
            }
        }
    
    def _get_llm_config(self) -> dict:
        """
        Get LLM configuration.
        Defaults to GPT-4.1-mini (User Request).
        Optional: Claude 3 Haiku via USE_CLAUDE env var.
        """
        use_claude = os.getenv("USE_CLAUDE", "false").lower() == "true"
        
        # Claude 3 Haiku (Optional - High Speed)
        if use_claude:
            anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
            if anthropic_key:
                logger.info("🧠 Using Anthropic Claude 3 Haiku")
                return {
                    "provider": {
                        "type": "anthropic",
                        "model": "claude-3-haiku-20240307",
                    },
                    "prompt": self._get_active_prompt(),
                    "functions": self._get_active_functions()
                }
            else:
                logger.error("❌ ANTHROPIC_API_KEY not set - falling back to GPT-4.1-mini")
        
        # Fallback/Default to OpenAI gpt-4o-mini (Primary)
        logger.info("🧠 Using OpenAI gpt-4.1-mini (Primary)")
        return {
            "provider": {
                "type": "open_ai",
                "model": "gpt-4.1-mini",
                "temperature": 0.45
            },
            "prompt": self._get_active_prompt(),
            "functions": self._get_active_functions()
        }
    
    
    def _get_active_prompt(self) -> str:
        """Get the active prompt based on tenant."""
        base_prompt = get_system_prompt(
            current_date=datetime.now(ZoneInfo("Australia/Perth" if self.tenant_id == "saranda" else "Australia/Melbourne")).strftime("%A, %d %B %Y"),
            current_time=datetime.now(ZoneInfo("Australia/Perth" if self.tenant_id == "saranda" else "Australia/Melbourne")).strftime("%I:%M %p"),
            tenant_id=self.tenant_id
        )
        
        # Smart Memory Injection
        memory_context = ""
        if self.memory["name"] or self.memory["order_summary"]:
            memory_context = f"\n\n=== CURRENT MEMORY (DO NOT FORGET) ===\n"
            if self.memory["name"]:
                memory_context += f"• Customer Name: {self.memory['name']}\n"
            if self.memory["order_summary"]:
                memory_context += f"• Current Order: {self.memory['order_summary']}\n"
            if self.memory["pickup_time"]:
                memory_context += f"• Desired Pickup: {self.memory['pickup_time']}\n"
            memory_context += "========================================\n"
        
        return base_prompt + memory_context
    
    def _get_active_functions(self) -> list:
        """Get the correct function definitions based on tenant."""
        if self.tenant_id == "saranda":
            return get_saranda_functions()
        elif self.tenant_id == "coalcreek":
            return get_coalcreek_functions()
        return get_booking_functions()
    
    def _get_active_greeting(self) -> str:
        """Get the active greeting based on tenant."""
        return get_random_greeting(self.tenant_id)
    
    def _get_tts_config(self) -> dict:
        """
        Get TTS configuration.
        Uses Cartesia Sonic-3 for ultra-low latency (~200ms).
        """
        # Look for custom voice ID in DB config
        voice_settings = self.tenant_config.get("voice_settings", {})
        voice_id = voice_settings.get("voice_id", CARTESIA_VOICE_ID)
        
        # MAP SLUGS TO UUIDS
        # Users might put readable names in DB config
        if voice_id == "cartesia-sonic-3-thalia":
            voice_id = "f786b574-daa5-4673-aa0c-cbe3e8534c02"
        elif len(voice_id) < 30: # Simple check for non-UUID
            logger.warning(f"⚠️ Invalid Voice ID format: {voice_id} - falling back to default")
            voice_id = CARTESIA_VOICE_ID
            
        logger.info(f"🎤 Using Cartesia Sonic-3 TTS (Voice ID: {voice_id})")
        return {
            "provider": {
                "type": "cartesia",
                "model_id": "sonic-3",
                "voice": {
                    "mode": "id",
                    "id": voice_id
                }
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
        self.is_demo_call = custom_params.get("is_demo", "false").lower() == "true"
        self.demo_type = custom_params.get("demo_type", "")
        
        # Adjust duration for Brand Rep mode
        if self.demo_type == "brand_rep":
            self.MAX_DEMO_DURATION_SECONDS = 300  # 5 minutes
            logger.info("🕒 Extended duration for Brand Rep demo (5 mins)")
            
        # START SENTINEL: Smart Greeting (only for demo calls)
        if self.is_demo_call:
             self.smart_greeting_task = asyncio.create_task(self._smart_greeting_logic())
            
        call_type = "DEMO" if self.is_demo_call else "PRODUCTION"
        
        # Multi-tenant: Resolve tenant_id
        explicit_tenant = custom_params.get("tenant_id")
        
        if explicit_tenant:
            self.tenant_id = explicit_tenant
        else:
            self.tenant_id = settings.TENANT_ID or "coalcreek" 
            
        # =====================================================================
        # CONFIG-DRIVEN ARCHITECTURE: Load settings from DB (ASYNC)
        # =====================================================================
        try:
            logger.info(f"📥 Loading config for tenant: {self.tenant_id}")
            self.tenant_config = await db_service.get_tenant_config(self.tenant_id)
            if not self.tenant_config:
                logger.warning(f"⚠️ No config found for {self.tenant_id}, using defaults")
        except Exception as e:
            logger.error(f"❌ Failed to load tenant config: {e}")
            self.tenant_config = {}
            
        # Set context for knowledge base
        set_tenant_context(self.tenant_id)
        
        # Initialize abuse protection
        self.abuse_protection = AbuseProtection(tenant_id=self.tenant_id)
        
        logger.info(f"🟢 Twilio stream started: {self.stream_sid} for {self.user_name} [{call_type}] tenant={self.tenant_id}")
        
        # Initialize timing
        self.call_start_time = time.time()
        self.abuse_protection.set_call_start_time(self.call_start_time)
        
        # =====================================================================
        # STRATEGY PATTERN: Select Dispatcher based on Config
        # =====================================================================
        pms_provider = self.tenant_config.get("integrations", {}).get("pms_provider")
        tenant_type = self.tenant_config.get("type", "motel")
        
        logger.info(f"🧩 Configuring Dispatcher | PMS: {pms_provider} | Type: {tenant_type}")
    
        if self.tenant_id == "saranda" or tenant_type == "restaurant":
            self.function_dispatcher = SarandaFunctionDispatcher(
                user_phone=self.user_phone,
                abuse_protection=self.abuse_protection,
                tenant_config=self.tenant_config
            )
            logger.info("✅ Using Saranda/Restaurant Dispatcher")
            
        elif self.tenant_id == "coalcreek" or pms_provider == "update 247":
            from .functions import CoalCreekFunctionDispatcher
            self.function_dispatcher = CoalCreekFunctionDispatcher(
                db_service=db_service,
                user_phone=self.user_phone,
                save_reservation_fn=self._save_motel_reservation,
                abuse_protection=self.abuse_protection
            )
            logger.info("✅ Using Coal Creek/update 247 Dispatcher")
            
        else:
            self.function_dispatcher = FunctionDispatcher(
                db_service=db_service,
                user_phone=self.user_phone,
                save_reservation_fn=self._save_motel_reservation,
                abuse_protection=self.abuse_protection,
                tenant_id=self.tenant_id
            )
            logger.info("✅ Using Generic Dispatcher")
        

        
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
                provider_config = settings_msg["agent"]["speak"]["provider"]
                model = provider_config.get("model") or provider_config.get("model_id", "unknown")
                logger.info(f"🎤 TTS PROVIDER: {tts_provider} (model: {model})")
            
            # Start background tasks
            asyncio.create_task(self._receive_from_deepgram())
            self.duration_monitor_task = asyncio.create_task(self._monitor_call_duration())
            
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram Agent: {e}")
            raise
    
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram Agent: {e}")
            raise

    async def _smart_greeting_logic(self):
        """
        Smart Wait for outbound calls:
        Wait for user to speak first (e.g., "Hello?").
        If silence for timeout (2.5s), assume user is waiting and break silence.
        """
        logger.info("⏳ Smart Wait: Waiting for user to speak first...")
        try:
            # Wait for 2.5 seconds
            await asyncio.sleep(2.5)
            
            # If user hasn't spoken yet, break the silence
            if not self.has_user_spoken:
                logger.info("⏰ Smart Wait timeout: User silent, injecting greeting")
                greeting = self._get_active_greeting()
                await self._inject_message(greeting)
            else:
                logger.info("🗣️ User spoke before timeout, letting conversation flow naturally")
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in smart greeting logic: {e}")
    
    async def _handle_twilio_media(self, data: dict):
        """Forward Twilio audio to Deepgram Agent."""
        # GO DEAF: Stop forwarding audio during hangup to ensure clean termination
        # This prevents the AI from hearing/responding to user's "bye" after we said farewell
        if getattr(self, '_is_hanging_up', False):
            return  # Silently drop audio - user won't be heard after farewell
        
        if not self.deepgram_ws:
            return
        
        try:
            # Twilio sends base64-encoded mulaw audio
            payload = data["media"]["payload"]
            audio_bytes = base64.b64decode(payload)
            
            # Forward raw audio to Deepgram
            await self.deepgram_ws.send(audio_bytes)
            
        except websockets.exceptions.ConnectionClosed:
            # Connection closed, stop trying to send
            return
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
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"🔌 Deepgram connection closed. Code: {e.code}, Reason: {e.reason}")
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
        # OPTIMIZATION: Use debug instead of info to reduce I/O latency
        logger.debug(f"📨 DG_EVENT: {event_type} | ai_speaking={ai_speaking} | full={event}")
        
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
            
            # ─────────────────────────────────────────────────────────────────
            # SMART HANGUP LOGIC:
            # If we are in the process of hanging up, check what the user said.
            # - If they said "bye", "thanks", etc. -> IGNORE IT (let hangup proceed)
            # - If they said "wait", "add X", etc. -> CANCEL HANGUP (resume chat)
            # ─────────────────────────────────────────────────────────────────
            if getattr(self, '_is_hanging_up', False):
                # STRICT ABUSE PROTECTION: If hanging up due to abuse, IGNORE ALL INPUT
                if getattr(self, 'call_outcome', '') == "abuse_timeout":
                    logger.info(f"🚫 Abuse termination in progress - ignoring user speech: '{content}'")
                    return

                content_lower = content.lower().strip()
                # Phrases that mean "I'm done too" - we should IGNORE these and let hangup finish
                reciprocal_farewells = [
                    "bye", "goodbye", "cya", "see ya", "see you", 
                    "thanks", "thank you", "thanks bye", "okay bye", "ok bye",
                    "have a good one", "cheers", "no thanks", "no that's all",
                    "no that's it", "that's it", "nope", "nah", "you too"
                ]
                
                # Check if it's a simple farewell (short & matches list)
                is_farewell = False
                if len(content_lower) < 20: 
                    if any(phrase in content_lower for phrase in reciprocal_farewells):
                        is_farewell = True
                
                if is_farewell:
                    logger.info(f"👋 User said farewell ('{content}') - ignoring to allow graceful hangup")
                    return # EXIT EARLY - do not process this text, do not reset hangup
                else:
                    logger.info(f"🛑 ABORT HANGUP: User said meaningful request ('{content}') - resuming conversation")
                    self._is_hanging_up = False
                    self._hangup_triggered = False
                    # Don't inject "I'm still here" - just reply naturally to their text
            
            # Track exchange
            self.exchange_count += 1
            self.transcript.append({
                "role": "user",
                "text": content,
                "timestamp": time.strftime("%H:%M:%S")
            })
            
            # Mark timing for response latency
            self.ai_response_start_time = time.time()
            self._stt_complete_time = time.time()  # For TRUE TTFT measurement
            self._first_ai_response_logged = False  # Reset for new utterance
            
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
                
                # TRUE TTFT: Log only for FIRST sentence after user spoke
                if hasattr(self, '_stt_complete_time') and not getattr(self, '_first_ai_response_logged', False):
                    ttft_ms = int((time.time() - self._stt_complete_time) * 1000)
                    logger.info(f"[AI]: {clean_content} (TTFT: {ttft_ms}ms)")
                    self._first_ai_response_logged = True
                else:
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
            
            # Semantic termination detection (Backup for explicit function calls)
            # If AI says goodbye, we should ensure the call actually ends
            termination_phrases = [
                # Explicit farewells
                "goodbye", "bye now", "bye bye", "bye!",
                # Time-based farewells (day/night/evening)
                "have a great day", "have a wonderful day", "have a lovely day", "enjoy your day",
                "have a great night", "have a wonderful night", "have a lovely night", "enjoy your night",
                "have a great evening", "have a wonderful evening", "have a lovely evening", "enjoy your evening",
                # Casual farewells
                "take care", "see you", "cheers", "catch you later", "thanks for calling", "thank you for calling",
                # Australian-style
                "have a good one", "all the best",
            ]
            lower_content = clean_content.lower()
            if any(phrase in lower_content for phrase in termination_phrases) and len(lower_content) < 80:
                logger.info(f"👋 AI indicated farewell ('{clean_content}') - scheduling hangup")
                # Mark as hanging up so duration monitor doesn't inject warnings
                self._is_hanging_up = True
                # Schedule hangup after estimated TTS duration
                wait_seconds = max(3, len(clean_content) / 12) + 2
                asyncio.create_task(self._scheduled_hangup(wait_seconds))
    
    async def _handle_user_started_speaking(self):
        """Handle VAD detection of user speech."""
        logger.info("🎤 User started speaking (VAD)")
        
        # Track timing
        self.user_speech_start_time = time.time()
        
        # Mark that user has spoken (for smart greeting logic)
        self.has_user_spoken = True
        
        # User spoke - exit any silence escalation cycle
        self._in_silence_escalation = False
        
        # ─────────────────────────────────────────────────────────────────
        # Note: We do NOT cancel hangup here anymore.
        # We wait for _handle_conversation_text to see what they said.
        # If they just said "bye", we want to let the hangup happen!
        # ─────────────────────────────────────────────────────────────────
        
        # Notify silence monitor
        self.silence_monitor.on_user_speech()
        
        # Send clear event to Twilio to stop agent audio immediately
        clear_message = {
            "event": "clear",
            "streamSid": self.stream_sid
        }
        await self.twilio_ws.send_json(clear_message)

        # CRITICAL: Force AI speaking state to False immediately
        # Deepgram might skip AgentAudioDone if interrupted, causing state lock
        self._ai_is_speaking = False
        self.silence_monitor.on_ai_finished_speaking() # Reset silence monitor state too
    
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

        # SMART MEMORY UPDATE
        # Capture details from function args to persist in prompt
        if "customer_name" in function_args and function_args["customer_name"]:
            self.memory["name"] = function_args["customer_name"]
            logger.info(f"🧠 Memory Updated: Name = {self.memory['name']}")
        
        if "items" in function_args:
             # Summarize items
            try:
                items = function_args["items"]
                summary_parts = []
                for item in items:
                    qty = item.get("quantity", 1)
                    name = item.get("name", "Item")
                    mods = item.get("modifiers", [])
                    mod_str = f" ({', '.join(mods)})" if mods else ""
                    summary_parts.append(f"{qty}x {name}{mod_str}")
                self.memory["order_summary"] = ", ".join(summary_parts)
                logger.info(f"🧠 Memory Updated: Order = {self.memory['order_summary']}")
            except Exception as e:
                logger.warning(f"Failed to parse memory items: {e}")

        if "pickup_time" in function_args:
            self.memory["pickup_time"] = function_args["pickup_time"]
        
        # Inject acknowledgment for slow/database tools to avoid silence
        # Inject acknowledgment for slow/database tools to avoid silence
        SLOW_TOOLS = [
            "report_missing_booking", 
            "create_booking", 
            "request_human_callback",
            "lookup_booking",
            "check_availability",
            "submit_order",     # Added for immediate feedback
            "get_menu_info"     # Added for immediate feedback
        ]
        
        # Track function processing state
        self._is_processing_function = True
        
        try:
            if function_name in SLOW_TOOLS:
                await self._inject_message(get_random_filler_prompt())
            
            # Execute via dispatcher
            result = await self.function_dispatcher.execute(function_name, function_args)
            
            # Capture system errors/outcome overrides
            if result.get("outcome_override"):
                self.call_outcome = result["outcome_override"]
                
                # Log error to transcript (visible in CRM)
                if result.get("error_details"):
                    self.transcript.append({
                        "role": "assistant",
                        "content": f"⚠️ [SYSTEM ERROR] {result['error_details']}",
                        "timestamp": datetime.now().isoformat()
                    })
                    logger.error(f"🚨 System Error logged to transcript: {result['error_details']}")
                    
                    # Create visible System Alert (Notification Center)
                    if result["outcome_override"] == "system_failure":
                        await db_service.create_system_alert(
                            title=f"Voice Agent Error: {function_name}",
                            message=result['error_details'],
                            severity="error",
                            component="voice_agent",
                            tenant_id=self.tenant_id,
                            metadata={
                                "call_sid": self.call_sid or "unknown",
                                "phone": self.user_phone,
                                "function": function_name
                            }
                        )
        finally:
            self._is_processing_function = False
        
        # Check for transfer signal
        if result.get("action") == "transfer":
            transfer_to = result.get("transfer_to")
            
            logger.info(f"📞 Transfer requested to {transfer_to}")
            
            # Execute transfer immediately - TwiML <Say> handles the message
            # (No need to inject via Deepgram - that causes race conditions)
            await self._execute_twilio_transfer(transfer_to)
            return  # Don't send function response, call is being transferred
        
        # Check for end_call signal (LLM explicitly requested call termination)
        if result.get("action") == "end_call":
            logger.info("👋 end_call function called - injecting farewell + scheduling hangup")
            self._is_hanging_up = True
            
            # Use pre-configured farewell for consistency (or custom message if provided)
            message = result.get("message")
            if not message:
                # Use tenant-specific pre-configured farewell (like greetings)
                message = get_random_farewell(self.tenant_id)
                logger.info(f"🗣️ Using pre-configured farewell: '{message}'")
            
            # Inject the farewell message
            await self._inject_message(message)
            
            # Schedule hangup after TTS completes (~15 chars/sec + buffer)
            delay = max(3.0, len(message) / 15) + 1.5
            logger.info(f"⏳ Farewell TTS ({len(message)} chars), hangup in {delay:.1f}s")
            asyncio.create_task(self._scheduled_hangup(delay))
            return  # Don't send function response, call is ending
        
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
                # Don't inject warning if we're already hanging up or call is completed
                if getattr(self, '_is_hanging_up', False) or self.call_outcome != "completed":
                    logger.debug("⏱️ Soft time warning skipped - call ending")
                    continue
                    
                logger.info(f"⏱️ Soft time warning [{call_type}]")
                await self._inject_message(duration_result.get("message", "We've been chatting for a while..."))
                
            elif action == "hard_cap":
                # Smart Wait: Let AI finish speaking or working
                wait_count = 0
                while (getattr(self, '_ai_is_speaking', False) or self._is_processing_function) and wait_count < 15:
                    if wait_count % 3 == 0:
                        logger.info(f"⏱️ Hard cap reached, waiting for AI to finish (busy={self._is_processing_function}, speaking={getattr(self, '_ai_is_speaking', False)})")
                    await asyncio.sleep(1)
                    wait_count += 1
                
                self.call_outcome = duration_result.get("outcome", "timeout_duration")
                
                # Check if we should transfer instead of hanging up
                # Production calls get transferred; Demo calls get polite hangup
                should_transfer = ABUSE_CONFIG.get("transfer_on_cap", False) and not self.is_demo_call
                
                if should_transfer:
                    logger.info(f"🚨 Duration cap reached - transferring to staff [{call_type}]")
                    # Clearer message about time limit
                    transfer_message = (
                        "We've reached the maximum duration for this automated call. "
                        "I'm going to transfer you to a staff member who can pick up right where we left off."
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
    
    async def _scheduled_hangup(self, delay: float):
        """Wait for a delay (TTS to finish) then hangup."""
        try:
            logger.info(f"⏳ Scheduled hangup in {delay:.1f}s")
            await asyncio.sleep(delay)
            await self._hangup_call()
        except Exception as e:
            logger.error(f"Scheduled hangup failed: {e}")

    async def _hangup_call(self):
        """Terminate the Twilio call gracefully."""
        # Prevent duplicate hangups
        if getattr(self, '_hangup_triggered', False):
            return
        self._hangup_triggered = True

        if not self.call_sid:
            logger.warning("Cannot hangup: No Call SID")
            return
        
        logger.info(f"📵 Hanging up call: {self.call_sid}")
        
        try:
            # ASYNC TWILIO CALL via httpx
            auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Calls/{self.call_sid}.json"
            data = {"Status": "completed"}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data, auth=auth)
                response.raise_for_status()
            
            logger.info("✅ Call terminated successfully")
            self.is_running = False
        except Exception as e:
            logger.error(f"Failed to hangup call: {e}")
    
    async def _scheduled_hangup(self, delay: float):
        """Wait for delay then hangup."""
        logger.info(f"⏳ Scheduled hangup in {delay}s")
        # Set flag immediately so we don't process more speech as interruption
        # unless it's a clear "No wait!" (handled by _handle_user_started_speaking)
        self._is_hanging_up = True
        
        await asyncio.sleep(delay)
        
        # Check if aborted
        if not getattr(self, '_is_hanging_up', True):
            logger.info("🛑 ABORT HANGUP: User spoke during scheduled hangup")
            return

        await self._hangup_call()

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
            await asyncio.sleep(3.5)
            
        except Exception as e:
            logger.warning(f"Failed to inject farewell: {e}")
        
        # ─────────────────────────────────────────────────────────────────
        # ABORT HANGUP CHECK: If user spoke during farewell, don't hang up!
        # _handle_user_started_speaking resets _is_hanging_up when user speaks.
        # ─────────────────────────────────────────────────────────────────
        if not getattr(self, '_is_hanging_up', True):
            logger.info("🛑 ABORT HANGUP: User spoke during farewell - resuming conversation")
            return  # User interrupted, don't hang up
        
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
            estimated_tts_time = max(3.5, len(farewell_message) // 10)
            logger.info(f"⏳ Waiting {estimated_tts_time}s for farewell TTS")
            await asyncio.sleep(estimated_tts_time)
        except Exception as e:
            logger.warning(f"Failed to send farewell: {e}")
        
        # ─────────────────────────────────────────────────────────────────
        # ABORT HANGUP CHECK: If user spoke during farewell, don't hang up!
        # ─────────────────────────────────────────────────────────────────
        if not getattr(self, '_is_hanging_up', True):
            logger.info("🛑 ABORT HANGUP: User spoke during farewell - resuming conversation")
            return  # User interrupted, don't hang up
        
        await self._hangup_call()
    
    async def _execute_twilio_transfer(self, transfer_to: str):
        """
        Execute Twilio call transfer using TwiML update.
        
        Uses <Say> then <Dial> to ensure transfer message is heard.
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
            
            # CRITICAL: Say transfer message FIRST via Twilio's TTS
            # This ensures the message plays BEFORE the dial starts
            # (Deepgram inject doesn't work - WebSocket gets disconnected before TTS completes)
            twiml.say(
                "Sure, I'll transfer you to our team now. Please hold.",
                voice="Polly.Joanna"  # AWS Polly voice for natural sound
            )
            
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
            
            # Update the live call with new TwiML via ASYNC httpx
            auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Calls/{self.call_sid}.json"
            data = {"Twiml": str(twiml)}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data, auth=auth)
                response.raise_for_status()
            
            logger.info(f"✅ Call transfer initiated to {transfer_to}")
            self.call_outcome = "transferred"
            self.is_running = False  # Stop AI processing during transfer
            
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            await self._inject_message("I'm sorry, I couldn't complete the transfer. Let me take a message instead.")

    
    # =========================================================================
    # DATABASE & CLEANUP
    # =========================================================================
    
    async def _save_motel_reservation(self, data: dict) -> dict:
        """Save reservation to motel_reservations collection using async httpx."""
        try:
            doc_id = ID.unique()
            headers = {
                "Content-Type": "application/json",
                "X-Appwrite-Project": settings.APPWRITE_PROJECT_ID,
                "X-Appwrite-Key": settings.APPWRITE_API_KEY
            }
            data["tenant_id"] = self.tenant_id
            url = f"{settings.APPWRITE_ENDPOINT}/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
            payload = {"documentId": doc_id, "data": data}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
                
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
                # ISOLATION: Check if this is a demo or a real tenant
                if self.tenant_id == "ovela_demo":
                     await db_service.create_demo_transcript(
                        phone=self.user_phone,
                        transcript=self.transcript,
                        exchange_count=self.exchange_count,
                        duration_seconds=duration,
                        outcome=self.call_outcome,
                        tenant_id=self.tenant_id,
                        call_sid=self.call_sid
                    )
                else:
                    # Tenant-Specific Storage
                    await db_service.save_call_transcript(
                        tenant_id=self.tenant_id,
                        call_sid=self.call_sid,
                        caller_phone=self.user_phone,
                        transcript=json.dumps(self.transcript), # save_call_transcript expects string
                        duration=duration,
                        status=self.call_outcome,
                        metadata={
                            "exchange_count": self.exchange_count,
                            "outcome": self.call_outcome
                        }
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
