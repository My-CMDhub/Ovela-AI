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

# Import from sibling modules
from .config import (
    DEEPGRAM_AGENT_URL,
    ABUSE_CONFIG,
    get_random_greeting,
    get_random_farewell,
    get_random_silence_prompt,
)
from .prompts import get_system_prompt
from .abuse_protection import AbuseProtection
from .silence_detection import SilenceMonitor
from .functions import get_booking_functions
from .functions.handlers import FunctionDispatcher, MOTEL_DB_ID
from .text_utils import prepare_for_tts, clean_tts_output

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
        
        # State tracking
        self.is_running = True
        self.call_start_time = None
        self.call_sid = None
        self.exchange_count = 0
        self.booking_completed = False
        
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
                    "prompt": get_system_prompt(
                        current_date=datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%A, %d %B %Y"),
                        current_time=datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%I:%M %p")
                    ),
                    "functions": get_booking_functions()
                },
                "speak": {
                    "provider": {
                        "type": "deepgram",
                        "model": "aura-2-thalia-en"
                    }
                },
                "greeting": get_random_greeting()
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
        
        # Extract custom parameters passed from TwiML
        custom_params = data["start"].get("customParameters", {})
        self.user_name = custom_params.get("user_name", "there")
        self.business_name = custom_params.get("business_name", "your business")
        self.user_phone = custom_params.get("user_phone", "unknown")
        
        logger.info(f"🟢 Twilio stream started: {self.stream_sid} for {self.user_name}")
        
        # Initialize timing
        self.call_start_time = time.time()
        self.abuse_protection.set_call_start_time(self.call_start_time)
        
        # Initialize function dispatcher with user context
        self.function_dispatcher = FunctionDispatcher(
            db_service=db_service,
            user_phone=self.user_phone,
            save_reservation_fn=self._save_motel_reservation,
            abuse_protection=self.abuse_protection
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
        
        if event_type == "Welcome":
            logger.info(f"🤝 Deepgram Agent welcome: {event}")
            
        elif event_type == "SettingsApplied":
            logger.info("⚙️ Deepgram Agent settings applied")
            
        elif event_type == "ConversationText":
            await self._handle_conversation_text(event)
            
        elif event_type == "UserStartedSpeaking":
            await self._handle_user_started_speaking()
            
        elif event_type == "AgentStartedSpeaking":
            logger.info("🔊 Agent started speaking")
            
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
            
            # Log clean content with latency info
            if self.ai_response_start_time:
                latency_ms = int((time.time() - self.ai_response_start_time) * 1000)
                logger.info(f"[AI]: {clean_content} (Response latency: {latency_ms}ms)")
            else:
                logger.info(f"[AI]: {clean_content}")
            
            # Save clean content to transcript (not raw with signals)
            self.last_ai_message = clean_content  # Track for silence detection TTS buffer
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
        
        # Notify silence monitor
        self.silence_monitor.on_user_speech()
        
        # Send clear event to Twilio to stop agent audio immediately
        clear_message = {
            "event": "clear",
            "streamSid": self.stream_sid
        }
        await self.twilio_ws.send_json(clear_message)
    
    async def _handle_agent_audio_done(self):
        """Handle agent finished speaking - start silence monitoring."""
        logger.info("🔇 Agent finished speaking")
        
        # Notify silence monitor with the AI message for TTS duration estimation
        last_message = getattr(self, 'last_ai_message', '')
        self.silence_monitor.on_ai_finished_speaking(last_message)
        check_id = self.silence_monitor.get_check_id()
        
        # Schedule silence check
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
        
        # Execute via dispatcher
        result = await self.function_dispatcher.execute(function_name, function_args)
        
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
        await asyncio.sleep(self.silence_monitor.get_soft_threshold())
        
        if not self.is_running:
            return
        
        result = self.silence_monitor.check_silence(check_id)
        action = result.get("action")
        
        if action == "soft_prompt":
            logger.info(f"⏱️ Soft silence - gentle check-in")
            await self._inject_message(result.get("prompt", get_random_silence_prompt()))
            asyncio.create_task(self._check_hard_silence(check_id))
            
        elif action == "abandon":
            self.call_outcome = "timeout_silence"
            await self._inject_farewell_and_hangup()
    
    async def _check_hard_silence(self, check_id: int):
        """Check for hard silence threshold (second follow-up)."""
        additional_wait = self.silence_monitor.get_hard_threshold() - self.silence_monitor.get_soft_threshold()
        await asyncio.sleep(additional_wait)
        
        if not self.is_running:
            return
        
        result = self.silence_monitor.check_silence(check_id)
        action = result.get("action")
        
        if action == "hard_prompt":
            logger.info(f"⏱️ Hard silence - urgent check-in")
            await self._inject_message(result.get("prompt", "Hello? Still there?"))
            asyncio.create_task(self._check_abandon_silence(check_id))
            
        elif action == "abandon":
            self.call_outcome = "timeout_silence"
            await self._inject_farewell_and_hangup()
    
    async def _check_abandon_silence(self, check_id: int):
        """Check for abandon threshold - end call if still silent."""
        additional_wait = self.silence_monitor.get_abandon_threshold() - self.silence_monitor.get_hard_threshold()
        await asyncio.sleep(additional_wait)
        
        if not self.is_running:
            return
        
        result = self.silence_monitor.check_silence(check_id)
        
        if result.get("action") == "abandon":
            logger.info(f"⏱️ Extended silence - ending call")
            self.call_outcome = "timeout_silence"
            await self._inject_farewell_and_hangup()
    
    # =========================================================================
    # DURATION MONITORING
    # =========================================================================
    
    async def _monitor_call_duration(self):
        """
        Background task that monitors call duration and enforces time caps.
        
        Uses thresholds from ABUSE_CONFIG:
        - soft_warning_minutes: Inject gentle "wrapping up" prompt
        - hard_cap_minutes: Force end call with polite farewell
        """
        logger.info(f"⏱️ Duration monitor started: soft={ABUSE_CONFIG['soft_warning_minutes']}min, hard={ABUSE_CONFIG['hard_cap_minutes']}min")
        
        while self.is_running:
            await asyncio.sleep(10)
            
            if not self.is_running or not self.call_start_time:
                break
            
            # Check duration using abuse protection
            duration_result = self.abuse_protection.check_duration()
            action = duration_result.get("action")
            
            if action == "soft_warning":
                logger.info(f"⏱️ Soft time warning")
                await self._inject_message(duration_result.get("message", "We've been chatting for a while..."))
                
            elif action == "hard_cap":
                logger.info(f"🚫 Hard time cap reached - ending call")
                self.call_outcome = duration_result.get("outcome", "timeout_duration")
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
        if not self.deepgram_ws:
            await self._hangup_call()
            return
        
        try:
            await self._inject_message(farewell_message)
            await asyncio.sleep(10)  # Longer wait for complex farewells
        except Exception as e:
            logger.warning(f"Failed to send farewell: {e}")
        
        await self._hangup_call()
    
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
                    outcome=self.call_outcome
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
