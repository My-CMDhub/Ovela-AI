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
    get_random_silence_farewell,
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
from .latency_tracker import LatencyTracker
from .memory import CallerMemoryBank
from services.motel_knowledge_base import set_tenant_context

CARTESIA_VOICE_ID = "f9836c6e-a0bd-460e-9d3c-f7299fa60f94"
# CARTESIA_VOICE_ID = "3e1ed423-17e5-4773-b87c-25b031106e41" - Paul AU
# CARTESIA_VOICE_ID = "a167e0f3-df7e-4d52-a9c3-f949145efdab" - Blake US
# CARTESIA_VOICE_ID = "47c38ca4-5f35-497b-b1a3-415245fb35e1" - Daniel US
# CARTESIA_VOICE_ID = "999df508-4de5-40a7-8bd3-8c12f678c284" - Layla US
# CARTESIA_VOICE_ID = "41f3c367-e0a8-4a85-89e0-c27bae9c9b6d" - Liam AU
# CARTESIA_VOICE_ID = "c63361f8-d142-4c62-8da7-8f8149d973d6" - Krishna IN
# CARTESIA_VOICE_ID = "f9836c6e-a0bd-460e-9d3c-f7299fa60f94" - Caroline US
# CARTESIA_VOICE_ID = "e8e5fffb-252c-436d-b842-8879b84445b6" - Cathy US - soft and slow

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


# ─────────────────────────────────────────────────────────────────────────────
# Module-level pure function — importable by tests without instantiating handler
# ─────────────────────────────────────────────────────────────────────────────

def trim_assistant_transcript(text: str, elapsed_seconds: float, wpm: int = 150) -> str:
    """
    Trim an assistant transcript entry to reflect only what the caller *actually heard*
    before a VAD interruption fired.

    Uses a fixed speech-rate estimate (default 150 WPM) to calculate the number
    of words delivered before the interruption. Trailing words that were generated
    but not yet spoken are pruned from the history so the LLM context stays
    coherent with the caller's actual auditory experience.

    This is a pure function with zero side effects — safe to call on the Hot Path.

    Args:
        text:             The full assistant message text that started playing.
        elapsed_seconds:  Seconds elapsed since TTS playback began (time.time() delta).
        wpm:              Estimated TTS delivery rate (default 150 WPM ≈ natural speech).

    Returns:
        Trimmed string containing only the words the caller heard.
        Returns "" if elapsed_seconds <= 0 or text is empty/whitespace.

    Example:
        >>> trim_assistant_transcript("Sure I can help you book a room.", 2.0, wpm=150)
        'Sure I can help you'  # 2s × 150÷60 = 5 words
    """
    if not text or not text.strip():
        return ""
    if elapsed_seconds <= 0:
        return ""

    words = text.split()
    words_spoken = int(elapsed_seconds * wpm / 60)  # floor via int()
    return " ".join(words[:words_spoken])


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
        
        # Latency tracking (for debugging/analytics)
        self.user_speech_start_time = None
        self.ai_response_start_time = None
        self.latency = LatencyTracker()
        self.latency.mark_call_start()
        
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
            "pickup_time": None,
            # Coal Creek motel booking context (session-only)
            "check_in": None,
            "check_out": None,
            "room_type": None,
            "num_guests": None,
            "notes": None,
        }
        
        # Order Tracking
        self.order_id = None
        self.pending_order = None # [NEW] Batch/Draft order buffer
        self._availability_cache = {}
        
        # Tenant Configuration (Database Driven)
        self.tenant_config = {}
        self._final_help_offer_active = False

        # Persistent Caller Memory Bank (error-contained — never crashes the hot path)
        self.caller_memory_bank = CallerMemoryBank()

    def _normalize_phrase(self, text: str) -> str:
        normalized = (text or "").lower()
        for char in ".,!?:;()-":
            normalized = normalized.replace(char, " ")
        return " ".join(normalized.split())

    def _contains_any_phrase(self, text: str, phrases: tuple[str, ...]) -> bool:
        padded = f" {text} "
        return any(f" {phrase} " in padded for phrase in phrases)

    def _is_explicit_terminal_goodbye(self, text: str) -> bool:
        normalized = self._normalize_phrase(text)
        if not normalized:
            return False
        explicit_goodbyes = (
            "bye",
            "goodbye",
            "bye bye",
            "see you",
            "see ya",
            "catch you later",
            "talk to you later",
            "farewell",
            "that's all",
            "that is all",
            "that's it",
            "that is it",
            "nothing else",
            "no more help",
            "i'm done",
            "im done",
            "all done",
            "i'm all set",
            "im all set",
            "that'll be all",
            "that will be all",
            "thanks bye",
            "thank you bye",
        )
        return self._contains_any_phrase(normalized, explicit_goodbyes)

    def _is_soft_close_only(self, text: str) -> bool:
        normalized = self._normalize_phrase(text)
        if not normalized or self._is_explicit_terminal_goodbye(normalized):
            return False
        soft_close_markers = (
            "thanks",
            "thank you",
            "cheers",
            "no worries",
            "appreciate it",
            "appreciated",
            "no thank you",
            "no thanks",
            "all good",
            "alright",
            "all right",
            "okay",
            "ok",
            "righto",
            "fair enough",
        )
        return self._contains_any_phrase(normalized, soft_close_markers)

    def _is_final_help_offer_message(self, text: str) -> bool:
        normalized = self._normalize_phrase(text)
        if not normalized:
            return False
        help_offer_markers = (
            "anything else i can help with",
            "anything else i can do for you",
            "anything else you need",
            "if you need anything else",
            "let me know if you need anything else",
            "still need anything else",
            "what else can i help with",
        )
        return self._contains_any_phrase(normalized, help_offer_markers)

    def _is_end_call_narration_message(self, text: str) -> bool:
        normalized = self._normalize_phrase(text)
        return normalized in {
            "i ll end the call now",
            "i will end the call now",
            "i ll hang up now",
            "i will hang up now",
            "ending the call now",
        }

    def _should_offer_one_more_help_before_hangup(self, user_utterance: str) -> bool:
        """
        UX gate: intercept the first LLM end_call for genuine callers.

        Rules:
        - Abusive/flagged callers (violation_count or off_topic_count > 0) → hang up immediately.
        - Final offer already spoken (loop guard) → hang up immediately.
        - Otherwise → intercept, offer one last help prompt, set loop guard.
        """
        # 1. Skip gate for abusive/flagged callers — hang up without soft offer.
        if self.abuse_protection and (
            getattr(self.abuse_protection, 'violation_count', 0) > 0
            or getattr(self.abuse_protection, 'off_topic_count', 0) > 0
        ):
            return False

        # 2. Loop guard — if we already offered, do not intercept a second time.
        if self._final_help_offer_active:
            return False

        # 3. Genuine first-close for a non-abusive caller → intercept.
        return True


    def _should_end_call_deterministically(self, user_utterance: str) -> bool:
        normalized = self._normalize_phrase(user_utterance)
        if not normalized or getattr(self, '_is_hanging_up', False):
            return False
        strongest_terminal_markers = (
            "bye",
            "goodbye",
            "bye bye",
            "see you",
            "see ya",
            "that's all",
            "that is all",
            "that's it",
            "that is it",
            "that'll be all",
            "that will be all",
        )
        return self._contains_any_phrase(normalized, strongest_terminal_markers)
    
    # =========================================================================
    # DEEPGRAM SETTINGS
    # =========================================================================
    
    def _get_settings_message(self) -> dict:
        """
        Build the Deepgram Voice Agent Settings message.
        
        This configures:
        - Audio encoding (mulaw for Twilio)
        - STT model (flux-general-en)
        - LLM (Google gemini-2.5-flash / gpt-4.1-nano edge-gateway)
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
        _stt_model = voice_settings.get("model", "nova-2")
        _endpointing = voice_settings.get("endpointing",
                        voice_settings.get("utterance_end_ms", 250 if "nova-3" in _stt_model else 300))

        # ── Domain vocabulary for accent-resilient STT ────────────────────────
        # Nova-2 uses 'keyterms' (flat list of strings).
        # Nova-3 uses 'vocabulary' (list of {"word": str} dicts).
        # Sending the wrong one is silently ignored — wasting the accuracy boost.
        # ─────────────────────────────────────────────────────────────────────
        _domain_terms = [
            "Coal Creek", "Chiltern", "Queen Room", "King Room",
            "Twin Room", "Family Room", "Deluxe Room", "Standard Room",
            "gmail", "hotmail", "yahoo", "outlook", "icloud",
            "booking", "check-in", "check-out",
        ]
        _stt_provider: dict = {
            "type": "deepgram",
            "model": _stt_model,
            "endpointing": _endpointing,
        }
        if "nova-3" in _stt_model:
            _stt_provider["vocabulary"] = [{"word": t} for t in _domain_terms]
        else:
            _stt_provider["keyterms"] = _domain_terms

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
                    "provider": _stt_provider
                },
                "think": self._get_llm_config(),
                "speak": self._get_tts_config(),
                "greeting": ""
            }
        }
    
    def _get_llm_config(self) -> dict:
        """
        Build the Deepgram Voice Agent think block.

        Model priority (highest → lowest):
          1. voice_settings.llm_model in tenant DB  
          2. LLM_MODEL env var (Cloud Run)             ← global override
          3. gemini-2.5-flash primary default

        All models below are Deepgram-managed — only your DEEPGRAM_API_KEY needed.

          Google   : gemini-2.5-flash*, gemini-2.5-flash-lite, gemini-2.0-flash
          OpenAI   : gpt-4.1-nano, gpt-4.1-mini, gpt-4o-mini
          Anthropic: claude-sonnet-4-6, claude-sonnet-4-5
          (* = current default)
        """
        voice_settings = self.tenant_config.get("voice_settings", {})

        db_model  = voice_settings.get("llm_model", "").strip()
        env_model = os.getenv("LLM_MODEL", "").strip()

        if db_model:
            llm_model, source = db_model, "DB"
        elif env_model:
            llm_model, source = env_model, "ENV"
        else:
            llm_model, source = "", "default"

        # Infer provider from model prefix
        if llm_model.startswith("claude-"):
            provider_type, model = "anthropic", llm_model
        elif llm_model.startswith("gemini-"):
            provider_type, model = "google", llm_model
        elif llm_model.startswith("gpt-") or llm_model.startswith("openai/"):
            provider_type, model = "open_ai", llm_model
        else:
            provider_type = "open_ai"
            model = "gpt-4.1-mini"
            source = "default"

        logger.info(f"🧠 LLM [{source}]: {provider_type} / {model}")

        return {
            "provider": {
                "type": provider_type,
                "model": model,
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
        _cc_booking = (
            self.tenant_id == "coalcreek" and
            any(self.memory[k] for k in ("check_in", "check_out", "room_type", "num_guests", "notes"))
        )
        if self.memory["name"] or self.memory["order_summary"] or _cc_booking:
            memory_context = f"\n\n=== CURRENT MEMORY (DO NOT FORGET) ===\n"
            if self.memory["name"]:
                memory_context += f"• Guest Name: {self.memory['name']}\n"
            if self.memory["order_summary"]:
                memory_context += f"• Current Order: {self.memory['order_summary']}\n"
            if self.memory["pickup_time"]:
                memory_context += f"• Desired Pickup: {self.memory['pickup_time']}\n"
            # Coal Creek booking details
            if self.tenant_id == "coalcreek":
                if self.memory["check_in"]:
                    memory_context += f"• Preferred Check-in: {self.memory['check_in']}\n"
                if self.memory["check_out"]:
                    memory_context += f"• Preferred Check-out: {self.memory['check_out']}\n"
                if self.memory["room_type"]:
                    memory_context += f"• Preferred Room Type: {self.memory['room_type']}\n"
                if self.memory["num_guests"]:
                    memory_context += f"• Number of Guests: {self.memory['num_guests']}\n"
                if self.memory["notes"]:
                    memory_context += f"• Special Requests / Notes: {self.memory['notes']}\n"
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
        voice_id = voice_settings.get("voice_id", "default")
        
        # MAP SLUGS TO UUIDS
        if voice_id in ("default"):
            voice_id = CARTESIA_VOICE_ID
        elif len(voice_id) < 30: # Simple check for non-UUID
            logger.warning(f"⚠️ Invalid Voice ID format: {voice_id} - falling back to default")
            voice_id = CARTESIA_VOICE_ID
            
        # Get dynamic speed and volume parameters for Cartesia provider
        speed = voice_settings.get("speed", 0.8)
        volume = voice_settings.get("volume", 0.8)
        
        logger.info(f"🎤 Using Cartesia Sonic-3 TTS (Voice ID: {voice_id}) | Speed: {speed} | Volume: {volume}")
        return {
            "provider": {
                "type": "cartesia",
                "model_id": "sonic-3",
                "speed": speed,
                "volume": volume,
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

        # Multi-tenant: Resolve tenant_id
        explicit_tenant = custom_params.get("tenant_id")
        self.tenant_id = explicit_tenant if explicit_tenant else (settings.TENANT_ID or "coalcreek")

        # =====================================================================
        # PLAY GREETING INSTANTLY: Stream pre-recorded greeting mulaw bytes 
        # from memory cache immediately to Twilio. While it plays, the async
        # database loading and Deepgram connection setup proceed in parallel.
        # =====================================================================
        transfer_failed = self.custom_params.get("transfer_failed") == "true"
        if transfer_failed:
            logger.info("🔊 Playing transfer_failed greeting instantly from cache")
            asyncio.create_task(self._speak_system_message(
                "Sorry about that, it looks like no one is available. How can I help you instead?",
                clip_key="transfer_failed"
            ))
        else:
            logger.info("🔊 Playing smart_greeting instantly from cache")
            asyncio.create_task(self._speak_system_message(
                self._get_active_greeting(),
                clip_key="smart_greeting"
            ))

        # =====================================================================
        # ASYNC INIT: Fetch profile and tenant config concurrently
        # Reduces cold start TTFT latency by not blocking sequentially.
        # =====================================================================
        try:
            logger.info(f"📥 Loading config for tenant: {self.tenant_id} and profile for {self.user_phone[:4]}****")
            caller_profile, tenant_config = await asyncio.gather(
                self.caller_memory_bank.get_profile(self.user_phone),
                db_service.get_tenant_config(self.tenant_id),
                return_exceptions=True
            )
            
            # Handle profile result
            if isinstance(caller_profile, Exception):
                logger.error("🧠 CallerMemoryBank unexpected error in handler: %s", caller_profile)
            elif caller_profile:
                if caller_profile.get("name"):
                    self.memory["name"] = caller_profile["name"]
                    logger.info("🧠 Returning guest recognised: %s", self.user_phone[:4] + "****")
                if caller_profile.get("room_preference"):
                    self.memory["room_type"] = caller_profile["room_preference"]
            
            # Handle config result
            if isinstance(tenant_config, Exception):
                logger.error(f"❌ Failed to load tenant config: {tenant_config}")
                self.tenant_config = {}
            elif not tenant_config:
                logger.warning(f"⚠️ No config found for {self.tenant_id}, using defaults")
                self.tenant_config = {}
            else:
                self.tenant_config = tenant_config
                
        except Exception as e:
            logger.error(f"❌ Failed in concurrent init: {e}")
            self.tenant_config = {}
            
        # Multi-tenant detection
        self.is_demo_call = custom_params.get("is_demo", "false").lower() == "true"
        self.demo_type = custom_params.get("demo_type", "")
        
        # Adjust duration for Brand Rep mode
        if self.demo_type == "brand_rep":
            self.MAX_DEMO_DURATION_SECONDS = 300  # 5 minutes
            logger.info("🕒 Extended duration for Brand Rep demo (5 mins)")
            
        call_type = "DEMO" if self.is_demo_call else "PRODUCTION"
            
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
            # Pass the in-process ADK orchestrator so perform_live_search queries
            # it directly instead of making a loopback HTTP POST to Cloud Run.
            _adk_orchestrator = getattr(getattr(self.twilio_ws, 'app', None), 'state', None)
            _adk_orchestrator = getattr(_adk_orchestrator, 'adk_orchestrator', None)
            self.function_dispatcher = CoalCreekFunctionDispatcher(
                db_service=db_service,
                user_phone=self.user_phone,
                save_reservation_fn=self._save_motel_reservation,
                abuse_protection=self.abuse_protection,
                caller_memory_bank=self.caller_memory_bank,
                call_sid=self.call_sid or "",
                adk_orchestrator=_adk_orchestrator,
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
            self.latency.mark_deepgram_connected()
            
            # Send Settings message
            settings_msg = self._get_settings_message()
            await self.deepgram_ws.send(json.dumps(settings_msg))
            logger.info("📤 Sent Settings to Deepgram Agent")
            self.latency.mark_settings_sent()
            
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
                await self._speak_system_message(greeting, clip_key="smart_greeting")
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
        
        # AUDIO PASSTHROUGH DURING FUNCTION CALLS:
        # Audio continues to flow to Deepgram so meaningful user corrections
        # ("wait, actually I mean next week") are transcribed and reach the LLM.
        # The Twilio 'clear' guard lives in _handle_user_started_speaking —
        # that is what protects injected TTS audio from being wiped.
        
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
            # Set exact playback start time if not set yet for this utterance
            if getattr(self, '_ai_is_speaking', False) and not getattr(self, '_tts_playback_started_this_turn', False):
                self._tts_playback_start = time.time()
                self._tts_playback_started_this_turn = True

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
            self.latency.mark_first_audio_out()  # no-op after first frame per turn
            
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
            self.latency.log_setup_latency()
            
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
            # Log with latency info.
            # NOTE: "turn_ms" = VAD start → transcript ready.  For real-time STT
            # this INCLUDES speech duration — the actual transcription overhead
            # is roughly utterance_end_ms (~300ms) + transit, which is NOT
            # separately observable via the Deepgram Voice Agent API.
            # Long utterances showing e.g. 4000ms are expected: most are speaking time.
            if self.user_speech_start_time:
                turn_ms = int((time.time() - self.user_speech_start_time) * 1000)
                logger.info(f"[User]: {content} (turn_ms incl. speech: {turn_ms}ms)")
            else:
                logger.info(f"[User]: {content}")
            
            # ─────────────────────────────────────────────────────────────────
            # HEURISTIC FILTER DURING FUNCTION CALLS:
            # Audio now flows to Deepgram while a tool is executing so that
            # genuine corrections ("wait, I meant next week") are transcribed
            # and land in the LLM context before the function result arrives.
            #
            # Filter rules:
            #  ≤ 2 words → filler noise ("okay", "uh huh", "yeah") → discard
            #  > 2 words → meaningful correction → let Deepgram context carry
            #              it; the LLM will address it when responding to the
            #              function result.  Add to local transcript for analytics.
            # ─────────────────────────────────────────────────────────────────
            if self._is_processing_function:
                word_count = len(content.strip().split())
                if word_count <= 2:
                    logger.debug(f"🙉 Short noise during function call ({word_count}w) — discarded")
                    return
                # Meaningful correction: record locally but skip all state
                # changes — the LLM sees it via Deepgram's conversation context.
                logger.info(f"📝 Meaningful correction during function call ({word_count}w) — LLM will handle post-result")
                self.transcript.append({
                    "role": "user",
                    "text": content,
                    "timestamp": time.strftime("%H:%M:%S")
                })
                return
            
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
            self._filler_played_this_turn = False   # Reset so first tool call this turn gets a filler
            self.latency.mark_stt_complete()
            # Tag turn type from content for grouped latency stats
            _words = content.split()
            if self._is_explicit_terminal_goodbye(content) or self._is_soft_close_only(content):
                self.latency.set_turn_type("goodbye")
            elif len(_words) <= 7:
                self.latency.set_turn_type("short_answer")
            else:
                self.latency.set_turn_type("long_answer")
            
            # Check for spam/abuse
            spam_result = self.abuse_protection.check_spam_behavior(content)
            if spam_result.get("is_spam"):
                if spam_result.get("should_hangup"):
                    self.call_outcome = "spam_terminated"
                    await self._hangup_with_farewell(spam_result.get("message", "Take care!"))
                    return
                elif spam_result.get("warning"):
                    await self._speak_system_message(spam_result["warning"], clip_key="abuse_warning")

            if self._should_end_call_deterministically(content):
                farewell = get_random_farewell(self.tenant_id)
                logger.info("👋 Deterministic end-call for explicit close: '%s'", content)
                await self._hangup_with_farewell(farewell)
                return

        elif role == "assistant":
            # GATING: If we are in the process of hanging up (e.g. end_call triggered),
            # ignore any subsequent text generation from the LLM to prevent
            # "silent hangup" where explanation overwrites farewell audio.
            if getattr(self, '_is_hanging_up', False):
                logger.info(f"🤐 Ignoring AI text during hangup: '{content[:30]}...'")
                return

            # Extract control signals and clean content for logging/transcript
            clean_content, signals = prepare_for_tts(content)

            if self._normalize_phrase(clean_content).strip(".!") in {"end call", "end_call"}:
                logger.info("🤐 Suppressing literal tool phrase from assistant output")
                return
            if self._is_end_call_narration_message(clean_content):
                logger.info("🤐 Suppressing end-call narration from assistant output")
                return
            
            # STATE MACHINE: AI is now speaking
            # This replaces AgentStartedSpeaking which Deepgram doesn't send
            self._ai_is_speaking = True
            self._tts_playback_started_this_turn = False
            
            # During escalation, preserve check ID so hard/abandon checks stay valid
            in_escalation = getattr(self, '_in_silence_escalation', False)
            self.silence_monitor.on_ai_started_speaking(preserve_check_id=in_escalation)
            
            # Don't reset escalation flag - let the escalation sequence continue
            
            # Log clean content with latency info
            if self.ai_response_start_time:
                latency_ms = int((time.time() - self.ai_response_start_time) * 1000)
                
                # TRUE TTFT: Log only for the first assistant sentence after user speech.
                if hasattr(self, '_stt_complete_time') and not getattr(self, '_first_ai_response_logged', False):
                    ttft_ms = int((time.time() - self._stt_complete_time) * 1000)
                    self._first_ai_response_logged = True
                    self.latency.mark_llm_first_token()
                    logger.info(f"[Ovela]: {clean_content} (TTFT: {ttft_ms}ms)")
                else:
                    logger.info(f"[Ovela]: {clean_content} (inter-sentence: {latency_ms}ms)")
                
                # Reset for per-sentence measurement (prevents compounding)
                self.ai_response_start_time = time.time()
            else:
                logger.info(f"[Ovela]: {clean_content}")
            
            # Save clean content to transcript (not raw with signals)
            self.last_ai_message = clean_content
            self._final_help_offer_active = self._is_final_help_offer_message(clean_content)
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
        # CLEAR-EVENT GUARD: While a function is executing we suppress the Twilio
        # 'clear' event so injected TTS audio (filler phrases) cannot be wiped.
        # Audio still flows to Deepgram — see _handle_twilio_media.
        # Meaningful corrections are filtered in _handle_conversation_text.
        if self._is_processing_function:
            logger.debug("🛡️ Suppressing Twilio clear during function call (TTS guard)")
            return
        
        # FILLER PROTECTION: Ignore user noise during injected filler playback
        if getattr(self, '_blocking_interruptions', False):
            logger.info("🎤 User started speaking during filler - IGNORING (Block Interruptions)")
            return

        # ─────────────────────────────────────────────────────────────────
        # POST-ACK DEAF WINDOW: After the agent plays an ACK filler
        # ("One moment, let me check..."), the audio is still playing in
        # the caller's earpiece for ~2.5s after Twilio's buffer drains.
        # Short affirmations said during that window ("okay", "sure",
        # "no worries", "yep") must NOT trigger a full clear-event that
        # wipes the AI's processing state.
        #
        # Gate: suppress Twilio clear if ALL of the following are true:
        #   1. We are within 2.5s of the last ACK filler TTS completing
        #   2. The ConversationText word-count gate (≤2 words) will handle
        #      the transcript-level filtering — we only suppress the clear.
        # Real interruptions that arrive after the window pass through normally.
        # ─────────────────────────────────────────────────────────────────
        _ack_done = getattr(self, '_ack_tts_done_at', None)
        _ACK_WINDOW_S = 2.5
        if _ack_done and (time.time() - _ack_done) < _ACK_WINDOW_S:
            logger.info(
                "🙉 VAD fired within ACK window (%.2fs ago) — suppressing Twilio clear "
                "(word-count gate in ConversationText will still filter transcript)",
                time.time() - _ack_done,
            )
            # Still update VAD timing state so latency tracking stays accurate
            self.user_speech_start_time = time.time()
            self.latency.mark_user_vad()
            self.has_user_spoken = True
            return
        
        logger.info("🎤 User started speaking (VAD)")
        
        # Track timing
        self.user_speech_start_time = time.time()
        self.latency.mark_user_vad()
        
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

        # INTERRUPTION TRIM: Prune last AI transcript entry to only include
        # words actually spoken before the interruption, keeping LLM context
        # coherent with what the caller heard. Pure math — zero I/O.
        tts_start = getattr(self, '_tts_playback_start', None)
        if tts_start and self.transcript and self.transcript[-1].get('role') == 'ai':
            elapsed = time.time() - tts_start
            original_text = self.transcript[-1].get('text', '')
            trimmed = trim_assistant_transcript(original_text, elapsed)
            if trimmed != original_text:
                self.transcript[-1]['text'] = trimmed
                logger.info(
                    "✂️ Interruption trim: %.1fs elapsed → %d→%d words | '%s…'",
                    elapsed,
                    len(original_text.split()),
                    len(trimmed.split()) if trimmed else 0,
                    trimmed[:40] if trimmed else "(empty)",
                )
                
                # INJECT SYSTEM TAG
                if self.deepgram_ws:
                    try:
                        inject_msg = {
                            "type": "InjectUserMessage",
                            "content": "[System Note: Caller interrupted. Continue from last confirmed point.]"
                        }
                        await self.deepgram_ws.send(json.dumps(inject_msg))
                        logger.info("💉 Injected interruption system tag into Deepgram context")
                    except Exception as e:
                        logger.warning(f"Failed to inject system tag: {e}")

        # CRITICAL: Force AI speaking state to False immediately
        # Deepgram might skip AgentAudioDone if interrupted, causing state lock
        self._ai_is_speaking = False
        self._tts_playback_started_this_turn = False
        self._final_help_offer_active = False
        # NOTE: do NOT call on_ai_finished_speaking() here — it sets silence_check_start_time
        # to the moment user speaks, which races with the 300ms grace in _handle_agent_audio_done
        # and causes abandon-silence to fire even when user has spoken.
    
    async def _handle_agent_started_speaking(self):
        """
        Handle agent starting to speak - invalidate pending silence checks.
        
        This is critical for proper silence detection:
        - When AI starts responding, any pending silence checks from previous
          utterances must be invalidated
        - This prevents "silence while AI is speaking" false positives
        """
        logger.info("🔊 Agent started speaking")
        
        # Record exact TTS playback start time for interruption trimming.
        # When the user speaks (VAD fires), elapsed = now - _tts_playback_start.
        self._tts_playback_start = time.time()
        
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
        self.latency.mark_agent_done()
        self.latency.log_turn()
        
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

        # Guard: if user started speaking during the 300ms grace window, their speech
        # will trigger AI response → AgentAudioDone → a fresh silence check after that.
        # Skip now to avoid setting silence_check_start_time AFTER last_user_speech_time
        # (which would make has_user_spoken_since return False and fire abandon incorrectly).
        if self.user_speech_start_time and time.time() - self.user_speech_start_time < 0.5:
            logger.debug("⏱️ Skipping silence check - user spoke during grace period")
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
        self.latency.mark_func_request()
        self.latency.set_turn_type("tool_call")
        
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

        # COAL CREEK BOOKING MEMORY: Capture preferred dates, room type, guest
        # count and notes from check_availability and create_booking_request so
        # the AI never has to ask again mid-conversation.
        if self.tenant_id == "coalcreek":
            if function_args.get("check_in_date"):
                self.memory["check_in"] = function_args["check_in_date"]
                logger.info(f"🧠 Memory Updated: check_in = {self.memory['check_in']}")
            if function_args.get("check_out_date"):
                self.memory["check_out"] = function_args["check_out_date"]
                logger.info(f"🧠 Memory Updated: check_out = {self.memory['check_out']}")
            if function_args.get("room_type") and function_args["room_type"] != "any":
                self.memory["room_type"] = function_args["room_type"]
                logger.info(f"🧠 Memory Updated: room_type = {self.memory['room_type']}")
            if function_args.get("num_guests"):
                self.memory["num_guests"] = function_args["num_guests"]
                logger.info(f"🧠 Memory Updated: num_guests = {self.memory['num_guests']}")
            if function_args.get("notes"):
                self.memory["notes"] = function_args["notes"]
                logger.info(f"🧠 Memory Updated: notes = {self.memory['notes']}")
        
        # ─────────────────────────────────────────────────────────────────
        # FAST-START PATH: For check_availability we always need a filler
        # and the LLM is instructed not to speak one.  Inject the deterministic
        # preset phrase immediately (no grace-period wait) and start the
        # function execution without delay — the user hears "One moment…"
        # while the PMS call runs concurrently.
        #
        # OTHER SLOW TOOLS: keep a reduced 0.3s grace period so the LLM's
        # own brief filler can flush before the system fallback fires.
        # ─────────────────────────────────────────────────────────────────
        FAST_TOOLS = {"check_availability", "perform_live_search"}
        SLOW_TOOLS = [
            "report_missing_booking",
            "create_booking",
            "request_human_callback",
            "lookup_booking",
            "create_booking_request",
            "submit_order",
            "get_menu_info"
        ]
        
        try:
            long_wait_task = None
            fn_done_event = None

            if function_name in FAST_TOOLS:
                # Block interruptions and fire deterministic filler immediately.
                # Use asyncio.create_task so function execution starts right away.
                self._blocking_interruptions = True
                preset = get_preset_phrase(self.tenant_id, "availability_checking")
                if preset:
                    asyncio.create_task(
                        self._speak_system_message(preset, clip_key="filler_short", wait_for_playback=True)
                    )
                # ── Deaf window tuning per tool ───────────────────────────────
                # check_availability: PMS round-trip is ~1-2s → unlock after 2.5s
                # perform_live_search: Vertex grounding is ~3-5s → stay deaf for 9s
                # (long_wait_filler will play a "still checking" bridge if >5s anyway)
                if function_name == "perform_live_search":
                    asyncio.create_task(self._unlock_interruptions(9.0))
                else:
                    asyncio.create_task(self._unlock_interruptions(2.5))
                fn_done_event = asyncio.Event()
                long_wait_task = asyncio.create_task(self._long_wait_filler(fn_done_event, function_name))

            elif function_name in SLOW_TOOLS:
                # Block interruptions so filler isn't cut off by user noise/"mhm"
                self._blocking_interruptions = True
                # Let the LLM's filler TTS audio flush to Twilio (reduced from 0.5s)
                await asyncio.sleep(0.3)
                # Safety net: inject filler ONLY if LLM didn't speak one AND we haven't
                # already played one this user turn (prevents double-filler on multi-step
                # LLM tool calls within the same user utterance, e.g. lookup by ref then by email)
                if not getattr(self, '_ai_is_speaking', False) and not getattr(self, '_filler_played_this_turn', False):
                    filler = get_random_filler_prompt()
                    await self._speak_system_message(filler, clip_key="filler_short")
                    self._filler_played_this_turn = True
                # Unlock interruptions after filler TTS plays (~2.5s)
                asyncio.create_task(self._unlock_interruptions(2.5))
                # Schedule progressive "still checking" for very long waits
                fn_done_event = asyncio.Event()
                long_wait_task = asyncio.create_task(self._long_wait_filler(fn_done_event, function_name))
            
            # ── Execute via dispatcher ──────────────────────────────────────
            ctx = {
                "pending_order": self.pending_order,
                "availability_cache": self._availability_cache,
            }
            try:
                result = await self.function_dispatcher.execute(
                    function_name, function_args, context=ctx
                )
                self.latency.mark_func_exec_done()

            except Exception as dispatch_err:
                # ── Graceful Degradation: Schema Hallucination Guard ──────────
                # Catch pydantic ValidationError (LLM sent malformed JSON schema,
                # wrong date format, bad type) or any other tool crash.
                # Never let this surface as dead air — always return a safe
                # user-facing fallback that prompts clarification.
                err_type = type(dispatch_err).__name__
                err_msg = str(dispatch_err)

                if "ValidationError" in err_type or "validation" in err_msg.lower():
                    # Schema hallucination: the LLM sent malformed arguments.
                    # Ask the user to rephrase rather than dropping the call.
                    logger.warning(
                        "⚠️ ADK schema hallucination detected in %s — "
                        "ValidationError: %s. Returning safe clarification prompt.",
                        function_name,
                        err_msg[:200],
                    )
                    result = {
                        "success": False,
                        "message": (
                            "I didn't quite catch all the details I need. "
                            "Could you repeat the date or spelling for me?"
                        ),
                        "_degradation_reason": f"schema_hallucination:{err_type}",
                    }
                else:
                    # Generic tool failure: DB timeout, network error, etc.
                    logger.error(
                        "❌ Tool execution failed for %s — %s: %s",
                        function_name,
                        err_type,
                        err_msg[:300],
                    )
                    result = {
                        "success": False,
                        "message": (
                            "I'm having a little trouble with that right now. "
                            "Let me try something else, or I can take a note and "
                            "have someone follow up with you."
                        ),
                        "_degradation_reason": f"tool_failure:{err_type}",
                    }

            finally:
                # Always cancel the long-wait filler — even on error paths.
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
            # Availability fallback: if live calendar is unavailable, do not force
            # auto-transfer here. Let the AI transparently explain what happened
            # and ask permission before transfer.
            if function_name == "check_availability" and result.get("available") == "unknown":
                logger.info("ℹ️ Availability unknown - returning transparent fallback to AI (no forced transfer)")

            # Check for transfer signal
            if result.get("action") == "transfer":
                logger.warning("⚠️ No specific staff phone for tenant %s, using default.", self.tenant_id)
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
                user_utterance = result.get("user_utterance", "")
                if self._should_offer_one_more_help_before_hangup(user_utterance):
                    logger.info("↩️ Suppressing premature end_call for soft close: '%s'", user_utterance)
                    self._final_help_offer_active = True
                    soft_close_msg = "No problem, if you need anything else just let me know."
                    # ── Deterministic voice: never rely on LLM to read this back ─
                    # The LLM is in "shutdown mode" after calling end_call, so it
                    # won't speak unless we do it from the system audio lane.
                    await self._speak_system_message(soft_close_msg)
                    # ── Sync LLM context so it knows the system already spoke ────
                    if self.deepgram_ws:
                        try:
                            inject_msg = {
                                "type": "InjectUserMessage",
                                "content": (
                                    f"[System: end_call intercepted for soft close. "
                                    f"System already said: '{soft_close_msg}'. "
                                    f"Do NOT repeat this. Wait for the caller to respond.]"
                                )
                            }
                            await self.deepgram_ws.send(json.dumps(inject_msg))
                            logger.info("💉 Injected soft-close context tag into Deepgram")
                        except Exception as e:
                            logger.warning(f"Failed to inject soft-close tag: {e}")
                    result = {
                        "success": True,
                        "soft_close_redirected": True,
                        "message": soft_close_msg,
                    }
                else:
                    logger.info("👋 end_call function called - injecting farewell + scheduling hangup")
                    self._is_hanging_up = True
                    message = result.get("message")
                    if not message:
                        message = get_random_farewell(self.tenant_id)
                        logger.info(f"🗣️ Using pre-configured farewell: '{message}'")
                    # Use the pre-recorded farewell clip if available to eliminate Cartesia TTS network latency
                    # (falls back gracefully to live Cartesia TTS if missing).
                    await self._speak_system_message(message, clip_key="farewell")
                    delay = max(4.0, (len(message) * 0.1) + 2.0)
                    logger.info(f"⏳ Farewell TTS ({len(message)} chars), hangup in {delay:.1f}s")
                    asyncio.create_task(self._scheduled_hangup(delay))
                    return

            # Check for wait_on_request signal
            if result.get("action") == "wait_on_request":
                wait_seconds = result.get("duration_seconds", 90)
                reason = result.get("reason", "")
                logger.info(f"⏳ wait_on_request function called. Pausing silence detection for {wait_seconds}s. Reason: {reason}")
                
                self.silence_monitor.pause_silence(wait_seconds)



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
        """Send function result back to Deepgram (V1 API format).
        
        Sanitizes 'ai_should_say' and 'message' fields through clean_tts_output()
        before transmitting, so no unicode smart quotes, newlines, or markdown
        characters ever reach the Cartesia TTS synthesis pipeline.
        """
        if not self.deepgram_ws:
            return

        try:
            # ── TTS Sanitization: strip unicode + markdown from human-facing fields ──
            # These fields are used by Deepgram's LLM to construct the agent's spoken
            # response. Any curly quotes, em-dashes, or \n will be synthesized verbatim.
            sanitized = dict(result)
            for field in ("ai_should_say", "message", "error_message", "description"):
                if isinstance(sanitized.get(field), str):
                    sanitized[field] = clean_tts_output(sanitized[field])

            response = {
                "type": "FunctionCallResponse",
                "id": call_id,
                "name": function_name,
                "content": json.dumps(sanitized)
            }
            await self.deepgram_ws.send(json.dumps(response))
            self.latency.mark_func_response()
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
        
        if action == "none" and reason == "paused_on_request":
            # Reschedule this check for 10 seconds later while we are waiting
            logger.debug(f"⏱️ Silence check #{check_id} paused. Re-checking...")
            asyncio.create_task(self._check_silence(check_id))
            return
            
        if action == "soft_prompt":
            logger.info(f"⏱️ Soft silence - gentle check-in")
            self._in_silence_escalation = True  # Prevent new silence cycles during escalation
            await self._speak_system_message(
                result.get("prompt", get_random_silence_prompt()),
                clip_key="silence_soft",
            )
            # During escalation we keep the original silence timer/check id,
            # otherwise the hard stage compares against a fresh clock and never fires.
            asyncio.create_task(self._check_hard_silence(self.silence_monitor.get_check_id()))
            
        elif action == "abandon":
            self.call_outcome = "timeout_silence"
            await self._hangup_with_farewell(result.get("farewell", get_random_silence_farewell()))
    
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
            await self._speak_system_message(
                result.get("prompt", "Hello? Still there?"),
                clip_key="silence_hard",
            )
            # Same escalation chain: keep using the active check id/window.
            asyncio.create_task(self._check_abandon_silence(self.silence_monitor.get_check_id()))

        elif action == "abandon":
            self._in_silence_escalation = False
            self.call_outcome = "timeout_silence"
            await self._hangup_with_farewell(result.get("farewell", get_random_silence_farewell()))
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
            await self._hangup_with_farewell(result.get("farewell", get_random_silence_farewell()))
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
                await self._speak_system_message(
                    duration_result.get("message", "We've been chatting for a while..."),
                    clip_key="duration_soft",
                )
                
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
                    # No clip_key: Cartesia synthesises the *actual* per-call transparent
                    # message rather than the generic pre-recorded farewell clip.
                    await self._speak_system_message(farewell, wait_for_playback=True)
                    await self._hangup_call()
                
                break
    
    # =========================================================================
    # MESSAGING & CALL CONTROL
    # =========================================================================
    
    async def _long_wait_filler(self, fn_done: asyncio.Event, function_name: str = ""):
        """Inject long-wait helper audio while a function call is still running."""
        try:
            if function_name == "check_availability":
                await asyncio.sleep(10.0)
                if not fn_done.is_set():
                    self._blocking_interruptions = True
                    # clip_key=None forces direct Cartesia synthesis for a fixed progress message.
                    await self._speak_system_message(
                        "Still checking live availability now. Thanks for waiting.",
                        clip_key=None,
                    )
                    asyncio.create_task(self._unlock_interruptions(2.5))
                return

            await asyncio.sleep(8.0)
            if not fn_done.is_set():
                fillers = [
                    "Thanks for your patience, just a sec.",
                    "Still checking, won't be long.",
                    "Almost there, one more moment.",
                ]
                self._blocking_interruptions = True
                await self._speak_system_message(random.choice(fillers), clip_key="filler_long")
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
        voice_id = voice_settings.get("voice_id", "default")
        if voice_id in ("default"):
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
            logger.info("🎵 All required system clip keys available — zero-latency mode active")

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

        audio_bytes = self._load_cached_clip(clip_key)
        source = f"clip:{clip_key}" if audio_bytes else "cartesia"
        if not audio_bytes:
            audio_bytes = await self._synthesize_cartesia_mulaw(message)
            if not audio_bytes:
                logger.error(
                    "🔇 System audio failed | key=%s | reason=no_clip_and_tts_failed | cartesia_error=%s",
                    clip_key or "dynamic",
                    self._last_system_tts_error or "unknown",
                )
                return False

        try:
            self._blocking_interruptions = True
            self.silence_monitor.on_ai_started_speaking(preserve_check_id=True)
            duration = await self._send_system_audio(audio_bytes, reason=source)
            if wait_for_playback and duration > 0:
                await asyncio.sleep(max(0.35, duration + 0.15))
            return True
        except Exception as e:
            logger.error(f"🔇 System audio send failed: {e}")
            return False
        finally:
            self._blocking_interruptions = False
            # ─────────────────────────────────────────────────────────────────
            # ACK SUPPRESSION WINDOW: After a filler/ACK clip is sent to
            # Twilio's buffer, the audio is still playing in the caller's
            # earpiece for the next 2-3 seconds.  Stamp the finish time so
            # _handle_user_started_speaking can gate VAD-triggered Twilio
            # 'clear' events during that window ("okay", "sure", "no worries"
            # said right after hearing the ACK must not nuke the AI's state).
            # Only stamp for filler/ACK clips, not farewell or transfer audio.
            _is_filler_clip = clip_key and any(
                tag in clip_key for tag in ("filler", "availability", "checking")
            )
            if _is_filler_clip or (clip_key is None and self._is_processing_function):
                self._ack_tts_done_at = time.time()
                logger.debug("⏱️ ACK suppression window opened (%.1fs)", self._ack_tts_done_at)
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
            await self._speak_system_message(
                farewell_message,
                wait_for_playback=True,
            )
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
            await self._speak_system_message(
                "I'm sorry, I couldn't complete the transfer. Let me take a message instead.",
                clip_key="transfer_failed",
                wait_for_playback=True,
            )
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
            await self._speak_system_message(
                "I'm sorry, I couldn't complete the transfer. Let me take a message instead.",
                clip_key="transfer_failed",
                wait_for_playback=True,
            )

    
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
        self.latency.log_call_summary()
        

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
        using Google Gemini 2.5 Flash via Vertex AI after the call ends.
        """
        # Return cached summary if available (avoids re-generation on cleanup)
        if getattr(self, 'cached_summary', None):
            return self.cached_summary

        if not self.transcript or len(self.transcript) < 2:
            return ""

        try:
            from google import genai
            import asyncio
            
            client = genai.Client(
                vertexai=True,
                project=os.getenv("GOOGLE_CLOUD_PROJECT", "project-bd29d7f8-c65f-4597-b7b"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
            )
            
            # Format transcript for the summarizer
            transcript_text = "\n".join([f"{m['role'].upper()}: {m['text']}" for m in self.transcript])
            
            system_instruction = (
                "You are a helpful assistant that summarizes customer service calls. "
                "Provide an ultra-concise, 1-sentence summary of what happened in the call "
                "(e.g., 'Customer ordered 2 large pepperoni rooms for 7:30pm pickup'). Focus on the intent and result."
            )
            
            # Run in a threadpool to prevent blocking the async event loop
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=f"Summarize this call transcript:\n\n{transcript_text}",
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.3,
                    max_output_tokens=60
                )
            )
            
            summary = response.text.strip()
            logger.info(f"📝 Generated call summary: {summary}")
            self.cached_summary = summary
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate call summary: {e}")
            return ""

# Backwards compatibility alias
DeepgramAgentHandler = VoiceAgentHandler
