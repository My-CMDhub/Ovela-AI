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
from pathlib import Path
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
    get_preset_phrase,
)
from .prompts import get_system_prompt
from .abuse_protection import AbuseProtection
from .silence_detection import SilenceMonitor
from .functions import get_booking_functions, get_coalcreek_functions
from .functions.handlers import FunctionDispatcher, MOTEL_DB_ID
from .text_utils import prepare_for_tts, clean_tts_output
from services.motel_knowledge_base import set_tenant_context

CARTESIA_VOICE_ID = "a167e0f3-df7e-4d52-a9c3-f949145efdab"
# CARTESIA_VOICE_ID = "3e1ed423-17e5-4773-b87c-25b031106e41" - Paul AU
# CARTESIA_VOICE_ID = "a167e0f3-df7e-4d52-a9c3-f949145efdab" - Blake US
# CARTESIA_VOICE_ID = "47c38ca4-5f35-497b-b1a3-415245fb35e1" - Daniel US
# CARTESIA_VOICE_ID = "999df508-4de5-40a7-8bd3-8c12f678c284" - Layla US
# CARTESIA_VOICE_ID = "41f3c367-e0a8-4a85-89e0-c27bae9c9b6d" - Liam AU
# CARTESIA_VOICE_ID = "c63361f8-d142-4c62-8da7-8f8149d973d6" - Krishna IN

SYSTEM_AUDIO_DIR = Path(__file__).resolve().parent / "audio"
REQUIRED_SYSTEM_CLIP_KEYS = [
    "smart_greeting",
    "silence_soft",
    "silence_hard",
    "abuse_warning",
    "filler_short",
    "filler_long",
    "transfer",
    "transfer_failed",
    "farewell",
    "duration_soft",
]

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
        self.customer_id = None # Track Square Customer ID for order linking

        self.booking_completed = False
        
        # Smart Greeting State
        self.has_user_spoken = False
        self.smart_greeting_task = None
        
        # Function tracking
        self._is_processing_function = False
        self._twilio_audio_frames_sent = 0
        self._system_audio_cache = {}
        self._last_system_tts_error = None
        
        # Transfer state tracking
        self._transfer_pending = False
        self._transfer_tts_done = asyncio.Event()
        self._transfer_target = None
        self._tts_lock = asyncio.Lock()
        
        # Injection confirmation gate (for _inject_system_message → Cartesia fallback)
        self._injection_confirm_event: asyncio.Event | None = None
        
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
        self.call_reference = None # Unified reference for bookings/orders
        
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
        
        # Order Tracking
        self.order_id = None
        self.pending_order = None # [NEW] Batch/Draft order buffer
        
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
                        "endpointing": voice_settings.get("endpointing", 500),  
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
    
    
    def _get_function_call_instructions(self) -> str:
        """
        Instructions the LLM follows when making function calls.

        System-triggered fillers and status prompts are handled by the
        deterministic system-audio lane. Keep LLM output focused on
        user-facing results after tool execution.
        """
        return (
            "FUNCTION CALL RULES (MANDATORY):\n"
            "When calling a function, DO NOT speak extra filler before the call.\n"
            "The system layer handles wait messages and silence prompts.\n"
            "\n"
            "check_availability:\n"
            "  CRITICAL: If user asks about 'other options' or 'what's available', use room_type='any' to check ALL rooms in ONE call.\n"
            "  NEVER call check_availability multiple times for different room types — always use 'any' first.\n"
            "\n"
            "After the function returns a result, respond naturally with the information."
        )
    
    def _get_active_prompt(self) -> str:
        """Get the active prompt based on tenant."""
        base_prompt = get_system_prompt(
            current_date=datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%A, %d %B %Y"),
            current_time=datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%I:%M %p"),
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
        
        # Append function-call speaking rules to the prompt.
        # These go into agent.think.prompt (the ONLY valid place for 
        # LLM behavioral instructions in the Deepgram API).
        func_instructions = self._get_function_call_instructions()
        
        return base_prompt + memory_context + "\n\n" + func_instructions
    
    def _get_active_functions(self) -> list:
        """Get the correct function definitions based on tenant."""
        if self.tenant_id == "coalcreek":
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
        # put readable names in DB config
        if voice_id == "cartesia-sonic-3-thalia":
            voice_id = "a167e0f3-df7e-4d52-a9c3-f949145efdab"
        elif len(voice_id) < 30: # Simple check for non-UUID
            logger.warning(f"⚠️ Invalid Voice ID format: {voice_id} - falling back to default")
            voice_id = CARTESIA_VOICE_ID
            
        # Get dynamic speed (multiplier: 1.0 is default, 0.8 is slower)
        speed = voice_settings.get("speed", 1.0)
        
        logger.info(f"🎤 Using Cartesia Sonic-3 TTS (Voice ID: {voice_id}) | Speed: {speed}")
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

        # Startup diagnostics for deterministic system-audio lane
        self._log_system_audio_clip_health()
        
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
    
        if self.tenant_id == "coalcreek" or pms_provider == "update 247":
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
                logger.info("🎤 TTS PROVIDER: eleven_labs")
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
<<<<<<< HEAD
                await self._speak_system_message(greeting, clip_key="smart_greeting")
=======
                await self._inject_system_message(greeting)
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)
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
        
        # GO DEAF DURING FUNCTION CALLS: Prevent Deepgram VAD from detecting user
        # speech while we're injecting TTS messages.  Without this, the user saying
        # "Hello?" triggers UserStartedSpeaking which sends a Twilio 'clear' event
        # that wipes the injected TTS audio buffer before it plays.
        if self._is_processing_function:
            return
        
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
            self._twilio_audio_frames_sent += 1
            
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
            # NON-BLOCKING: Run function handler as a task so the receive loop
            # continues forwarding audio frames to Twilio.
            asyncio.create_task(self._handle_function_call(event))
            
        elif event_type == "InjectionRefused":
            logger.debug("ℹ️ InjectionRefused received (system lane no longer depends on it)")
            
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
<<<<<<< HEAD
                    await self._speak_system_message(spam_result["warning"], clip_key="abuse_warning")
=======
                    await self._inject_system_message(spam_result["warning"])
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)

        elif role == "assistant":
            # Fire injection confirmation gate if _inject_system_message is waiting
            if self._injection_confirm_event is not None and not self._injection_confirm_event.is_set():
                self._injection_confirm_event.set()

            # GATING: If we are in the process of hanging up (e.g. end_call triggered),
            # ignore any subsequent text generation from the LLM to prevent
            # "silent hangup" where explanation overwrites farewell audio.
            if getattr(self, '_is_hanging_up', False):
                logger.info(f"🤐 Ignoring AI text during hangup: '{content[:30]}...'")
                return

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
                    logger.info(f"[Ovela]: {clean_content} (TTFT: {ttft_ms}ms)")
                    self._first_ai_response_logged = True
                else:
                    logger.info(f"[Ovela]: {clean_content} (inter-sentence: {latency_ms}ms)")
                
                # Reset for per-sentence measurement (prevents compounding)
                self.ai_response_start_time = time.time()
            else:
                logger.info(f"[Ovela]: {clean_content}")
            
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
            
            # Semantic termination detection REMOVED
            # We now rely exclusively on the explicit 'end_call' function to hang up.
            # This prevents premature hangups on phrases like "Cheers" or "Have a good one".

    
    async def _handle_user_started_speaking(self):
        """Handle VAD detection of user speech."""
        # ─────────────────────────────────────────────────────────────────
        # GO DEAF DURING FUNCTION CALLS: If a function is in progress we
        # are injecting TTS ("One moment...").  VAD may still fire from
        # residual audio in Deepgram's buffer.  Do NOT send the Twilio
        # 'clear' event — it would wipe the injected TTS audio buffer
        # and the caller would hear silence.
        # ─────────────────────────────────────────────────────────────────
        if self._is_processing_function:
            logger.debug("🙉 Go Deaf: ignoring UserStartedSpeaking during function call")
            return
        
        # FILLER PROTECTION: Ignore user noise during injected filler playback
        if getattr(self, '_blocking_interruptions', False):
            logger.info("🎤 User started speaking during filler - IGNORING (Block Interruptions)")
            return
        
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
        logger.info("🔇 Agent audio done (transfer_pending=%s)", self._transfer_pending)
        
        # Mark AI as not speaking - transition to awaiting user
        self._ai_is_speaking = False
        
        # If we're waiting for transfer TTS to complete, signal it's done
        if self._transfer_pending:
            logger.info("✅ Transfer TTS playback completed – signalling _transfer_tts_done")
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

        # Attach last user utterance for deterministic date resolution in tools
        # (e.g., "upcoming weekend", "after 5 days") without prompt bloat.
        try:
            if isinstance(function_args, dict) and "_user_utterance" not in function_args:
                for entry in reversed(self.transcript):
                    if entry.get("role") == "user":
                        function_args["_user_utterance"] = entry.get("text", "")
                        break
        except Exception:
            pass
        
        if not function_name or not call_id:
            logger.error(f"❌ FunctionCallRequest missing name or id. Event: {event}")
            return
        
        # DEDUP GUARD: Prevent cascading duplicate calls while one is in progress.
        # When the receive loop was blocking, user retries ("Hello?") would pile up
        # and each trigger another function call on replay.
        if self._is_processing_function:
            logger.warning(f"⏭️ Skipping duplicate {function_name} – another function already in progress")
            await self._send_function_response(call_id, function_name, {
                "skipped": True,
                "message": "I'm already working on your request. One moment please."
            })
            return
        
        logger.info(f"🔧 Function call: {function_name}({function_args})")
        
        # Mark as processing BEFORE any async work to block duplicates immediately
        self._is_processing_function = True

        # SMART MEMORY UPDATE
        # Capture details from function args to persist in prompt
        if "customer_name" in function_args and function_args["customer_name"]:
            self.memory["name"] = function_args["customer_name"]
            logger.info(f"🧠 Memory Updated: Name = {self.memory['name']}")
        elif "name" in function_args and function_args["name"]:
            self.memory["name"] = function_args["name"]
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
        
        # ─────────────────────────────────────────────────────────────────
        # LLM-NATIVE FILLER: The LLM speaks preset phrases itself (via
        # function_call_instructions in Settings). We just need a brief
        # pause to let the LLM's TTS audio flush through to Twilio before
        # Go Deaf blocks further audio frames.
        # ─────────────────────────────────────────────────────────────────
        SLOW_TOOLS = [
            "report_missing_booking", 
            "create_booking", 
            "request_human_callback",
            "lookup_booking",
            "check_availability",
            "submit_order",
            "get_menu_info"
        ]
        
        try:
            long_wait_task = None
            fn_done_event = None

            if function_name in SLOW_TOOLS:
                # Block interruptions so filler isn't cut off by user noise/"mhm"
                self._blocking_interruptions = True
                # Let the LLM's filler TTS audio flush to Twilio
                await asyncio.sleep(0.5)
                # Safety net: inject filler if LLM didn't speak one
                if not getattr(self, '_ai_is_speaking', False):
                    filler = get_random_filler_prompt()
<<<<<<< HEAD
                    await self._speak_system_message(filler, clip_key="filler_short")
=======
                    await self._inject_system_message(filler)
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)
                # Unlock interruptions after filler TTS plays (~2.5s)
                asyncio.create_task(self._unlock_interruptions(2.5))
                
                # Schedule progressive "still checking" for very long waits
                fn_done_event = asyncio.Event()
                long_wait_task = asyncio.create_task(self._long_wait_filler(fn_done_event))
            
            # Execute via dispatcher
            ctx = {"pending_order": self.pending_order}
            result = await self.function_dispatcher.execute(function_name, function_args, context=ctx)
            
            # Cancel the long-wait filler if function completed
            if fn_done_event:
                fn_done_event.set()
            if long_wait_task and not long_wait_task.done():
                long_wait_task.cancel()
            
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
                        # Trigger Soft Transfer
                        asyncio.create_task(self._handle_system_failure(result['error_details']))
                        
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
        except Exception as func_err:
            logger.error(f"❌ Unexpected error in function call handling: {func_err}")
            result = {"success": False, "message": "I encountered a technical issue."}
        
        # ─────────────────────────────────────────────────────────────────
        # POST-FUNCTION LOGIC: Still under Go Deaf (_is_processing_function = True)
        # so injected speech cannot be wiped by Twilio 'clear' events.
        # Go Deaf is released in the finally block below.
        # ─────────────────────────────────────────────────────────────────
        
        try:
            # Availability fallback: if live calendar is unavailable, apologize and transfer
            if function_name == "check_availability" and result.get("available") == "unknown":
                message = result.get("hint") or get_preset_phrase(self.tenant_id, "availability_fail")
                await self._say_and_wait(message)
                await self._execute_twilio_transfer(
                    settings.STAFF_PHONE_NUMBER,
                    play_transfer_message=False,
                    backup_tts_message="Transferring you to reception now. One moment please.",
                )
                return

            # Check for transfer signal
            if result.get("action") == "transfer":
                import logging
                logging.getLogger(__name__).warning("⚠️ No specific staff phone for tenant %s, using default.", self.tenant_id)
                transfer_to = settings.STAFF_PHONE_NUMBER
                if not transfer_to and self.tenant_config.get("business_phone"):
                     transfer_to = self.tenant_config["business_phone"]
                logger.info(f"📞 Transfer requested to {str(transfer_to)[:2]}***{str(transfer_to)[-2:]}")
                message = result.get("message") or get_preset_phrase(self.tenant_id, "transfering")
                await self._speak_system_message(message, clip_key="transfer", wait_for_playback=True)
                await self._execute_twilio_transfer(transfer_to, play_transfer_message=False)
                return

            # Check for end_call signal (LLM explicitly requested call termination)
            if result.get("action") == "end_call":
                logger.info("👋 end_call function called - injecting farewell + scheduling hangup")
                self._is_hanging_up = True
                message = result.get("message")
                if not message:
                    message = get_random_farewell(self.tenant_id)
                    logger.info(f"🗣️ Using pre-configured farewell: '{message}'")
<<<<<<< HEAD
                await self._speak_system_message(message, clip_key="farewell")
=======
                await self._inject_system_message(message)
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)
                delay = max(4.0, (len(message) * 0.1) + 2.0)
                logger.info(f"⏳ Farewell TTS ({len(message)} chars), hangup in {delay:.1f}s")
                asyncio.create_task(self._scheduled_hangup(delay))
                return

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

            # Check for order completion
            if function_name == "submit_order":
                 if result.get("success") and result.get("action") == "hold":
                     self.pending_order = result.get("order_details")
                     logger.info(f"📝 Order Held in Batch: {len(self.pending_order.get('items', []))} items")
                 elif result.get("success") and result.get("order_id"):
                     self.order_id = result.get("order_id")
                     self.call_reference = self.order_id
                     logger.info(f"🛒 Order captured (Immediate): {self.order_id}")

            # Check for booking completion (Motel)
            if function_name == "create_booking_request" and result.get("success"):
                self.call_reference = result.get("booking_reference")
                logger.info(f"🏨 Booking captured: {self.call_reference}")

            # SMART MEMORY UPDATE: Capture Customer ID from Lookup
            if function_name == "lookup_customer" and result.get("found") and result.get("customer_id"):
                self.customer_id = result.get("customer_id")
                logger.info(f"🆔 Captured Customer ID: {self.customer_id}")

            # Send response back to Deepgram
            await self._send_function_response(call_id, function_name, result)
        
        finally:
            # Release Go Deaf AFTER all post-function speech & transfers are done
            self._is_processing_function = False
    
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
<<<<<<< HEAD
            await self._speak_system_message(
                result.get("prompt", get_random_silence_prompt()),
                clip_key="silence_soft",
            )
            # CRITICAL: get fresh check_id AFTER _speak_system_message returns.
            # on_ai_finished_speaking() inside it increments silence_check_id.
            # Passing the old stale id would cause check_silence() to return
            # action='none' (check_invalidated), silently killing the chain.
            asyncio.create_task(self._check_hard_silence(self.silence_monitor.get_check_id()))
=======
            await self._inject_system_message(result.get("prompt", get_random_silence_prompt()))
            # Continue escalation chain with same check_id
            asyncio.create_task(self._check_hard_silence(check_id))
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)
            
        elif action == "abandon":
            self.call_outcome = "timeout_silence"
            await self._hangup_with_farewell(random.choice([
                "I can't seem to hear you anymore. Feel free to call back if you need help. Take care!",
                "It seems like we've lost connection. Please call us back anytime. Goodbye!",
                "I haven't heard from you in a while. Please call back if you need assistance. Have a great day!",
            ]))
    
    async def _check_hard_silence(self, check_id: int):
        """Check for hard silence threshold (second follow-up)."""
        # Guard: Exit if AI started speaking or call already ending
        if getattr(self, '_ai_is_speaking', False) or getattr(self, '_is_hanging_up', False):
            self._in_silence_escalation = False
            return

        # Wait delta between soft and hard threshold
        hard_wait = self.silence_monitor.get_hard_threshold() - self.silence_monitor.get_soft_threshold()
        logger.info(f"⏱️ Hard silence check waiting {hard_wait}s")
        await asyncio.sleep(hard_wait)

        if not self.is_running or getattr(self, '_ai_is_speaking', False) or getattr(self, '_is_hanging_up', False):
            self._in_silence_escalation = False
            return

        result = self.silence_monitor.check_silence(check_id)
        action = result.get("action")

        if action == "hard_prompt":
            logger.info(f"⏱️ Hard silence - urgent check-in")
<<<<<<< HEAD
            await self._speak_system_message(
                result.get("prompt", "Hello? Still there?"),
                clip_key="silence_hard",
            )
            # Same as soft→hard: get fresh check_id after on_ai_finished_speaking incremented it
            asyncio.create_task(self._check_abandon_silence(self.silence_monitor.get_check_id()))

=======
            await self._inject_system_message(result.get("prompt", "Hello? Still there?"))
            asyncio.create_task(self._check_abandon_silence(check_id))
            
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)
        elif action == "abandon":
            self._in_silence_escalation = False
            self.call_outcome = "timeout_silence"
            await self._hangup_with_farewell(random.choice([
                "I can't seem to hear you anymore. Feel free to call back if you need help. Take care!",
                "It seems like we've lost connection. Please call us back anytime. Goodbye!",
                "I haven't heard from you in a while. Please call back if you need assistance. Have a great day!",
            ]))
        else:
            # User spoke or check invalidated - exit escalation
            self._in_silence_escalation = False
    
    async def _check_abandon_silence(self, check_id: int):
        """Check for abandon threshold - end call if still silent."""
        # Guard: Exit if AI started speaking or call already ending
        if getattr(self, '_ai_is_speaking', False) or getattr(self, '_is_hanging_up', False):
            self._in_silence_escalation = False
            return

        abandon_wait = self.silence_monitor.get_abandon_threshold() - self.silence_monitor.get_hard_threshold()
        logger.info(f"⏱️ Abandon silence check waiting {abandon_wait}s")
        await asyncio.sleep(abandon_wait)

        if not self.is_running or getattr(self, '_ai_is_speaking', False) or getattr(self, '_is_hanging_up', False):
            self._in_silence_escalation = False
            return
        
        result = self.silence_monitor.check_silence(check_id)
        
        if result.get("action") == "abandon":
            logger.info(f"⏱️ Extended silence ({int(result.get('duration', 0))}s) - ending call")
            self._in_silence_escalation = False
            self.call_outcome = "timeout_silence"
            await self._hangup_with_farewell(random.choice([
                "I can't seem to hear you anymore. Feel free to call back if you need help. Take care!",
                "It seems like we've lost connection. Please call us back anytime. Goodbye!",
                "I haven't heard from you in a while. Please call back if you need assistance. Have a great day!",
            ]))
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
<<<<<<< HEAD
                await self._speak_system_message(
                    duration_result.get("message", "We've been chatting for a while..."),
                    clip_key="duration_soft",
                )
=======
                await self._inject_system_message(duration_result.get("message", "We've been chatting for a while..."))
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)
                
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
                should_transfer = ABUSE_CONFIG.get("transfer_on_cap", False) and not self.is_demo_call
                if should_transfer:
                    logger.info(f"🚨 Duration cap reached - transferring to staff [{call_type}]")
                    
                    # GO DEAF MECHANISM: Stop listening immediately to prevent interruptions
                    logger.info("🙉 'Go Deaf' activated: Ignoring input during transfer explanation")
                    self._is_hanging_up = True
                    
                    # 1. Honest Message
                    msg = "This is getting a bit complex. I'll put you through to the team now."
                    await self._say_and_wait(msg)
                    
                    # 2. PROACTIVE SUMMARY SMS (Blocking/Sync)
                    try:
                        logger.info("Generating summary for Hard Cap SMS...")
                        # Ensure we have a summary BEFORE sending
                        try:
                            await self._generate_call_summary()
                        except Exception as e:
                            logger.error(f"Summary generation failed (proceeding to transfer): {e}")
                        
                        logger.info("📨 Sending Hard Cap Summary SMS (Blocking)...")
                        
                        # Build context
                        intent = self.memory.get("order_summary") or "Customer Inquiry"
                        sms_context = ""
                        if self.pending_order:
                             items = ", ".join([f"{i['quantity']}x {i['name']}" for i in self.pending_order.get('items', [])])
                             sms_context = f" | DRAFT: {items}"
                        
                        summary_msg = f"⏱️ HARD CAP TRANSFER: {self.user_phone} ({self.user_name or 'Unknown'}). Context: {intent}{sms_context}"
                        
                        # Use immediate dispatch & AWAIT it
                        from services.sms import sms_service
                        from core.config import settings
                        
                        await sms_service.send_sms(
                             to_number=settings.STAFF_PHONE_NUMBER,
                             message=summary_msg
                        )
                        logger.info("✅ Hard Cap Summary SMS Sent.")
                    except Exception as e:
                        logger.error(f"Failed to send hard cap summary: {e}")

                    # 3. Wait for TTS to play (Extended Delay)
                    # 4. Transfer (Skip internal SMS since we just sent it)
                    await self._execute_twilio_transfer(settings.STAFF_PHONE_NUMBER, skip_summary_sms=True, play_transfer_message=False)
                else:
                    logger.info(f"🚫 Hard time cap reached - ending call [{call_type}]")
                    # GO DEAF: Stop processing user audio to prevent InjectionRefused
                    self._is_hanging_up = True
                    farewell = duration_result.get("farewell", "Thanks for calling!")
                    await self._speak_system_message(farewell, clip_key="farewell", wait_for_playback=True)
                    await self._hangup_call()
                
                break
    
    # =========================================================================
    # MESSAGING & CALL CONTROL
    # =========================================================================
    
    async def _long_wait_filler(self, fn_done: asyncio.Event):
        """Inject extra filler if a function call takes > 8s."""
        try:
            await asyncio.sleep(8.0)
            if not fn_done.is_set():
                fillers = [
                    "Thanks for your patience, just a sec.",
                    "Still checking, won't be long.",
                    "Almost there, one more moment.",
                ]
                self._blocking_interruptions = True
<<<<<<< HEAD
                await self._speak_system_message(random.choice(fillers), clip_key="filler_long")
=======
                await self._inject_system_message(random.choice(fillers))
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)
                asyncio.create_task(self._unlock_interruptions(2.5))
        except asyncio.CancelledError:
            pass
    
    async def _unlock_interruptions(self, delay: float):
        """Helper to unlock interruptions after a delay (lets filler TTS play fully)."""
        try:
            await asyncio.sleep(delay)
            self._blocking_interruptions = False
        except asyncio.CancelledError:
            pass
    
    def _get_cartesia_voice_id(self) -> str:
        voice_settings = self.tenant_config.get("voice_settings", {})
        voice_id = voice_settings.get("voice_id", CARTESIA_VOICE_ID)
        if voice_id == "cartesia-sonic-3-thalia":
            return CARTESIA_VOICE_ID
        if len(voice_id) < 30:
            return CARTESIA_VOICE_ID
        return voice_id

    def _get_clip_path(self, clip_key: str | None) -> Path | None:
        if not clip_key:
            return None
        voice_id = self._get_cartesia_voice_id()
        preferred = SYSTEM_AUDIO_DIR / voice_id / f"{clip_key}.mulaw.raw"
        fallback = SYSTEM_AUDIO_DIR / "default" / f"{clip_key}.mulaw.raw"
        if preferred.exists():
            return preferred
        if fallback.exists():
            return fallback
        return None

    def _log_system_audio_clip_health(self):
        """Log missing/available system clip keys for the active voice at startup."""
        voice_id = self._get_cartesia_voice_id()
        voice_dir = SYSTEM_AUDIO_DIR / voice_id
        default_dir = SYSTEM_AUDIO_DIR / "default"

        missing_keys = []
        voice_keys = []
        default_keys = []

        for clip_key in REQUIRED_SYSTEM_CLIP_KEYS:
            voice_file = voice_dir / f"{clip_key}.mulaw.raw"
            default_file = default_dir / f"{clip_key}.mulaw.raw"
            if voice_file.exists():
                voice_keys.append(clip_key)
            elif default_file.exists():
                default_keys.append(clip_key)
            else:
                missing_keys.append(clip_key)

        logger.info(
            "🎵 System-audio clip health | voice_id=%s | voice=%d | default=%d | missing=%d",
            voice_id,
            len(voice_keys),
            len(default_keys),
            len(missing_keys),
        )

        if missing_keys:
            logger.warning(
                "🎵 Missing system clip keys (will fallback to live Cartesia): %s",
                ", ".join(missing_keys),
            )
        else:
            logger.info("🎵 All required system clip keys available")

    def _load_cached_clip(self, clip_key: str | None) -> bytes | None:
        clip_path = self._get_clip_path(clip_key)
        if not clip_path:
            return None
        cache_key = str(clip_path)
        if cache_key in self._system_audio_cache:
            return self._system_audio_cache[cache_key]
        try:
            clip_bytes = clip_path.read_bytes()
            if clip_bytes:
                self._system_audio_cache[cache_key] = clip_bytes
                return clip_bytes
        except Exception as e:
            logger.warning(f"🎵 Failed to load system clip {clip_path.name}: {e}")
        return None

    async def _synthesize_cartesia_mulaw(self, text: str, timeout: float = 1.6) -> bytes | None:
        if not settings.CARTESIA_API_KEY or not text:
            self._last_system_tts_error = "CARTESIA_API_KEY missing or empty text"
            return None
        voice_id = self._get_cartesia_voice_id()
        payload = {
            "model_id": "sonic-3",
            "transcript": text,
            "voice": {"mode": "id", "id": voice_id},
            "output_format": {
                "container": "raw",
                "encoding": "pcm_mulaw",
                "sample_rate": 8000,
            },
            "language": "en",
        }
        headers = {
            "X-API-Key": settings.CARTESIA_API_KEY,
            "Cartesia-Version": "2025-04-16",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post("https://api.cartesia.ai/tts/bytes", headers=headers, json=payload)
                response.raise_for_status()
                self._last_system_tts_error = None
                return response.content
        except Exception as e:
            self._last_system_tts_error = str(e)
            logger.warning(f"🎵 Cartesia system TTS failed: {e}")
            return None

    async def _send_system_audio(self, audio_bytes: bytes, reason: str = "system") -> float:
        if not audio_bytes or not self.stream_sid:
            return 0.0
        payload = base64.b64encode(audio_bytes).decode("utf-8")
        media_message = {
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": payload},
        }
        await self.twilio_ws.send_json(media_message)
        self._twilio_audio_frames_sent += 1
        duration = len(audio_bytes) / 8000.0
        logger.info(f"🔊 System audio played ({reason}) bytes={len(audio_bytes)} dur={duration:.2f}s")
        return duration

    async def _speak_system_message(
        self,
        message: str,
        clip_key: str | None = None,
        wait_for_playback: bool = False,
    ) -> bool:
        if not message:
            return False

<<<<<<< HEAD
        audio_bytes = self._load_cached_clip(clip_key)
        source = f"clip:{clip_key}" if audio_bytes else "cartesia"
        if not audio_bytes:
            audio_bytes = await self._synthesize_cartesia_mulaw(message)
            if not audio_bytes:
                logger.error(
                    "🔇 System audio failed | key=%s | reason=no_clip_and_tts_failed | cartesia_error=%s",
                    clip_key or "dynamic",
                    self._last_system_tts_error or "unknown",
=======
    async def _inject_system_message(self, content: str) -> bool:
        """
        Send a system-initiated message to the caller.

        Strategy:
          1. Send InjectAgentMessage to Deepgram.
          2. Wait up to 2.5s for ConversationText(role=assistant) confirmation.
          3. No confirmation → Cartesia /tts/bytes fallback (direct to Twilio).

        The confirmation event is fired in _handle_conversation_text when
        role == 'assistant'. injection_sent_at uses time.time() (wall clock)
        so the user-spoke guard compares the same clock domain as
        self.user_speech_start_time.
        """
        if not self.deepgram_ws or not content:
            return False

        confirm_event = asyncio.Event()
        self._injection_confirm_event = confirm_event
        injection_sent_at = time.time()  # wall clock — must match user_speech_start_time

        try:
            await self.deepgram_ws.send(json.dumps({
                "type": "InjectAgentMessage",
                "content": content
            }))
            logger.info(f"📨 InjectAgentMessage sent ({len(content)} chars): '{content[:60]}'")
        except Exception as e:
            logger.error(f"📨 InjectAgentMessage FAILED: {e}")
            self._injection_confirm_event = None
            await self._cartesia_tts_direct(content)
            return True

        try:
            await asyncio.wait_for(confirm_event.wait(), timeout=2.5)
            logger.info("✅ Injection confirmed by Deepgram (ConversationText received)")
            return True
        except asyncio.TimeoutError:
            # Guard: if user spoke AFTER injection was sent, skip Cartesia playback
            # (avoid talking over the user's words). Both timestamps use time.time().
            if self.user_speech_start_time and self.user_speech_start_time > injection_sent_at:
                logger.info("🙉 Cartesia fallback skipped — user spoke during injection wait")
                return True
            logger.warning(f"⚠️ Injection unconfirmed after 2.5s — Cartesia fallback: '{content[:60]}'")
            await self._cartesia_tts_direct(content)
            return True
        finally:
            self._injection_confirm_event = None

    async def _cartesia_tts_direct(self, text: str) -> bool:
        """
        Synthesize speech via Cartesia /tts/bytes and stream µ-law bytes
        directly to Twilio. Used as fallback when Deepgram InjectAgentMessage
        is not confirmed within the 2.5s window.
        """
        if not settings.CARTESIA_API_KEY or not text:
            logger.error("🎤 Cartesia direct: CARTESIA_API_KEY missing or empty text")
            return False

        payload = {
            "model_id": "sonic-3",
            "transcript": text,
            "voice": {"mode": "id", "id": CARTESIA_VOICE_ID},
            "output_format": {
                "container": "raw",
                "encoding": "pcm_mulaw",
                "sample_rate": 8000,
            },
            "language": "en",
        }
        headers = {
            "X-API-Key": settings.CARTESIA_API_KEY,
            "Cartesia-Version": "2025-04-16",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    "https://api.cartesia.ai/tts/bytes",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                audio_bytes = resp.content
            if audio_bytes:
                await self._send_audio_to_twilio(audio_bytes)
                dur = len(audio_bytes) / 8000.0
                logger.info(f"🎤 Cartesia direct TTS OK: {len(audio_bytes)} bytes ({dur:.1f}s) for '{text[:40]}'")
                return True
            logger.error("🎤 Cartesia direct TTS: empty response")
            return False
        except Exception as e:
            logger.error(f"🎤 Cartesia direct TTS FAILED: {e}")
            return False

    async def _prompt_agent_to_speak(self, message: str):
        """Make the agent speak by updating its prompt with an urgent instruction.
        
        Uses Deepgram's UpdatePrompt — the LLM processes the instruction and
        speaks through the reliable ConversationText → TTS → Twilio path.
        This works regardless of agent/user state (unlike InjectAgentMessage).
        """
        if not self.deepgram_ws:
            logger.warning("📢 UpdatePrompt SKIP: websocket closed")
            return
        try:
            update = {
                "type": "UpdatePrompt",
                "prompt": (
                    self._get_active_prompt()
                    + f'\n\n⚠️ URGENT SYSTEM INSTRUCTION (OVERRIDE ALL OTHER RULES): '
                    f'Say this IMMEDIATELY, word for word, as your next response: "{message}"'
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)
                )
                return False

        try:
            self._blocking_interruptions = True
<<<<<<< HEAD
            self.silence_monitor.on_ai_started_speaking(preserve_check_id=True)
            duration = await self._send_system_audio(audio_bytes, reason=source)
            if wait_for_playback and duration > 0:
                await asyncio.sleep(max(0.35, duration + 0.15))
            return True
=======
            success = await self._inject_system_message(message)
            if success:
                logger.info(f"⏳ _say_and_wait: waiting {estimated_wait:.1f}s for TTS")
                await asyncio.sleep(estimated_wait)
                elapsed = time.monotonic() - start
                logger.info(f"✅ _say_and_wait: done in {elapsed:.1f}s")
            else:
                logger.warning("❌ _say_and_wait: injection failed")
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)
        except Exception as e:
            logger.error(f"🔇 System audio send failed: {e}")
            return False
        finally:
            self._blocking_interruptions = False
            # preserve_escalation=True during silence escalation so on_ai_finished_speaking
            # does NOT reset silence_followup_count (which would break the chain).
            self.silence_monitor.on_ai_finished_speaking(
                preserve_escalation=getattr(self, '_in_silence_escalation', False)
            )

    async def _prompt_agent_to_speak(self, message: str):
        """Compatibility wrapper: system-triggered messages use deterministic system audio lane."""
        await self._speak_system_message(message)

    async def _say_and_wait(self, message: str):
        """Play system message and block until playback window has passed."""
        await self._speak_system_message(message, wait_for_playback=True)
    

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

    async def _hangup_with_farewell(self, farewell_message: str):
        """Speak a system farewell then hang up."""
        self._is_hanging_up = True

        start = time.monotonic()
        try:
<<<<<<< HEAD
            await self._speak_system_message(
                farewell_message,
                clip_key="farewell",
                wait_for_playback=True,
            )
=======
            self._blocking_interruptions = True
            await self._inject_system_message(farewell_message)
            # Wait for audio to finish after injection/Cartesia streamed to Twilio
            estimated_wait = max(2.0, (len(farewell_message) / 12) + 1.0)
            logger.info(f"⏳ _hangup_with_farewell: waiting {estimated_wait:.1f}s for audio playback")
            await asyncio.sleep(estimated_wait)
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)
            elapsed = time.monotonic() - start
            logger.info(f"✅ _hangup_with_farewell: done in {elapsed:.1f}s")
        except Exception as e:
            elapsed = time.monotonic() - start
            logger.error(f"❌ _hangup_with_farewell: FAILED after {elapsed:.1f}s — {e}")
        
        # ABORT CHECK: if user spoke during farewell, don't hang up
        if not getattr(self, '_is_hanging_up', True):
            logger.info("🛑 ABORT HANGUP: User spoke during farewell - resuming")
            return
        
        await self._hangup_call()
    
    async def _handle_system_failure(self, error_msg: str):
        """
        Handle critical system failures (e.g., tool crash, API down).
        Apologize to user and transfer to human.
        """
        logger.error(f"🚨 Handling System Failure: {error_msg}")
        
        # 1. Apologize
        apology = "Sorry, I'm having a technical issue. I'll put you through to a human now."
        await self._say_and_wait(apology)
        
        # 2. Prevent further AI processing
        self._is_hanging_up = True # Block new text
        self._is_processing_function = True # Block new functions
        
        # 4. Transfer
        staff_number = settings.STAFF_PHONE_NUMBER
        await self._execute_twilio_transfer(
            staff_number,
            play_transfer_message=False,
            backup_tts_message="Transferring you now. One moment.",
        )
        
        # 5. Log outcome
        self.call_outcome = "system_failure_transfer"

    async def _execute_twilio_transfer(
        self,
        transfer_to: str,
        skip_summary_sms: bool = False,
        play_transfer_message: bool = True,
        backup_tts_message: str | None = None,
    ):
        """
        Execute Twilio call transfer using TwiML update.
        
        Uses <Say> then <Dial> to ensure transfer message is heard.
        Falls back to AI if no answer within TRANSFER_TIMEOUT.
        
        Args:
            backup_tts_message: Optional safety-net message played via Twilio
                TTS if Deepgram/Cartesia TTS may not have been audible.
        """
        if not self.call_sid:
            logger.warning("Cannot transfer: No Call SID")
<<<<<<< HEAD
            await self._speak_system_message(
                "I'm sorry, I couldn't complete the transfer. Let me take a message instead.",
                clip_key="transfer_failed",
                wait_for_playback=True,
            )
=======
            await self._inject_system_message("I'm sorry, I couldn't complete the transfer. Let me take a message instead.")
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)
            return
        
        logger.info(f"📞 Executing transfer to {'*' * (len(transfer_to) - 2)}{transfer_to[-2:]}")

        # [NEW] SEND TRANSFER SUMMARY SMS (Non-blocking)
        if not skip_summary_sms:
            try:
                # Check for pending order to include context
                sms_context = ""
                if self.pending_order:
                    items = ", ".join([f"{i['quantity']}x {i['name']}" for i in self.pending_order.get('items', [])])
                    sms_context = f" | DRAFT ORDER: {items}"
                
                # Default intent if none
                intent = self.memory.get("order_summary") or "Customer Inquiry"
                
                from services.sms import sms_service
                summary_msg = f"📞 INCALL TRANSFER: {self.user_phone} ({self.user_name or 'Unknown'}). Context: {intent}{sms_context}"
                
                # Fire and forget (don't delay transfer significantly)
                # But use 'create_task' to ensure it runs
                asyncio.create_task(sms_service.send_sms(
                    to_number=settings.STAFF_PHONE_NUMBER, # Always alert main staff number
                    message=summary_msg
                ))
                logger.info("📨 Transfer summary SMS queued")
            except Exception as e:
                logger.warning(f"Failed to queue transfer SMS: {e}")

        try:
            from twilio.twiml.voice_response import VoiceResponse, Dial
            
            # Build TwiML for transfer
            twiml = VoiceResponse()
            
            # Optional transfer message via Twilio's TTS
            if play_transfer_message:
                twiml.say(
                    "Sure, I'll transfer you to our team now. Please hold.",
                    voice="Polly.Joanna"  # AWS Polly voice for natural sound
                )
            elif backup_tts_message:
                # Safety-net: if AI TTS might not have been audible, play a
                # short Twilio TTS so the caller isn't transferred in silence.
                twiml.say(backup_tts_message, voice="Polly.Joanna")
            
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
            
            masked_to = f"{'*' * (len(transfer_to) - 4)}{transfer_to[-4:]}" if len(transfer_to) > 4 else transfer_to
            logger.info(f"✅ Call transfer initiated to {masked_to}")
            self.call_outcome = "transferred"
            self.is_running = False  # Stop AI processing during transfer
            
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
<<<<<<< HEAD
            await self._speak_system_message(
                "I'm sorry, I couldn't complete the transfer. Let me take a message instead.",
                clip_key="transfer_failed",
                wait_for_playback=True,
            )
=======
            await self._inject_system_message("I'm sorry, I couldn't complete the transfer. Let me take a message instead.")
>>>>>>> 229338c (feat: applied direct cartesia TTS & fix dead air issue)

    
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
                        booking_ref=self.call_reference,
                        status=self.call_outcome,
                        call_summary=await self._generate_call_summary(),
                        customer_name=self.memory.get("name"),
                        metadata={
                            "exchange_count": self.exchange_count,
                            "outcome": self.call_outcome,
                            "order_id": self.order_id
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


    async def _generate_call_summary(self) -> str:
        """
        Generates a concise 1-sentence summary of the call transcript 
        using a dedicated model after the call ends.
        """
        return ""  # Disabled for testing — remove this line to re-enable

        # Return cached summary if available (avoids re-generation on cleanup)
        if getattr(self, 'cached_summary', None):
            return self.cached_summary

        if not self.transcript or len(self.transcript) < 2:
            return ""

        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Format transcript for the summarizer
            transcript_text = "\n".join([f"{m['role'].upper()}: {m['text']}" for m in self.transcript])
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini", # Dedicated efficient model for summarizing
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes customer service calls. Provide a ultra-concise, 1-sentence summary of what happened in the call (e.g. 'Customer ordered 2 large pepperoni pizzas for 7:30pm pickup'). Focus on the intent and result."},
                    {"role": "user", "content": f"Summarize this call transcript:\n\n{transcript_text}"}
                ],
                max_tokens=60,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info(f"📝 Generated call summary: {summary}")
            self.cached_summary = summary
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate call summary: {e}")
            return ""

# Backwards compatibility alias
DeepgramAgentHandler = VoiceAgentHandler
