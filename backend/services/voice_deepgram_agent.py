"""
Deepgram Voice Agent Bridge for Twilio.

This bridges Twilio Media Streams to Deepgram's Voice Agent API.
Deepgram handles: STT (flux) + LLM (OpenAI) + TTS (Aura-2) + VAD/Interruption

Architecture:
    Twilio ←─ Media Stream ─→ Your Server ←─ WebSocket ─→ Deepgram Agent API
"""

import json
import logging
import asyncio
import base64
import time
import random
import re
import websockets
from twilio.rest import Client
from fastapi import WebSocket
from core.config import settings
from services.appwrite import db_service

logger = logging.getLogger(__name__)

# Deepgram Voice Agent API endpoint
DEEPGRAM_AGENT_URL = "wss://agent.deepgram.com/v1/agent/converse"

# Dynamic Australian-tone greetings for natural variety
GREETINGS_POOL = [
    "G'day! Lydoun Motel, Ovela speaking. How can I help you today?",
    "Good day! The Lydoun Motel, this is Ovela. What can I do for you?",
    "Hello there! You've reached The Lydoun Motel. I'm Ovela, how can I help?",
    "Ovela is here, speaking from Lydoun Motel. How can I assist you?",
    "Hi there! This is Ovela at The Lydoun Motel. What can I help you with?",
]

# Varied silence check-in prompts for natural feel
SILENCE_PROMPTS = [
    "Hello? Still there?",
    "Can you hear me alright?",
    "Take your time, I'm here when you're ready.",
    "No rush, just checking you're still on the line.",
    "Hello? Are you still with me?",
]

# Fast, warm farewell styles
FAREWELL_STYLES = [
    "No worries, have a great one! feel free to reach out us when needed",
    "Cheers, take care! feel free to call use whenever needed. Have a greate day",
    "All good, thanks for calling!",
    "Beauty, catch you later! Thanks for calling",
    "Thanks for calling, have a lovely day! Bye",
]

# Silence detection thresholds (in seconds) - ONLY counts when user is NOT speaking
SOFT_SILENCE_THRESHOLD = 10   # First gentle check-in prompt
HARD_SILENCE_THRESHOLD = 20   # More urgent check
ABANDON_THRESHOLD = 25        # End call

# =============================================================================
# ABUSE PROTECTION CONFIG - Easy to switch between DEMO and PRODUCTION
# =============================================================================
ENVIRONMENT = "demo"  # Change to "production" for prod settings

# Demo settings (stricter for testing)
DEMO_CONFIG = {
    "context_pairs": 6,           # Conversation pairs to remember
    "soft_warning_minutes": 5,    # Gentle "wrapping up" prompt
    "hard_cap_minutes": 8,        # Maximum call duration
    "off_topic_limit": 5,         # flag_off_topic calls before auto-hangup
    "human_escalation": False,    # No human escalation in demo
}

# Production settings (more lenient, with human escalation)
PROD_CONFIG = {
    "context_pairs": 8,           # More context for pattern detection
    "soft_warning_minutes": 8,    # More time for complex bookings
    "hard_cap_minutes": 12,       # Higher limit with escalation
    "off_topic_limit": 5,         # Same threshold
    "human_escalation": True,     # Log for human follow-up
}

# Active config based on environment
ABUSE_CONFIG = DEMO_CONFIG if ENVIRONMENT == "demo" else PROD_CONFIG

# Context patterns that indicate user might need thinking time
THINKING_PATTERNS = [
    "what dates", "when would", "how many", "which room",
    "would you like", "do you need", "can you tell me",
    "let me know", "think about", "decide",
]

# Spam detection patterns (indicative of non-genuine callers)
SPAM_PATTERNS = [
    # Gibberish/nonsense
    r'^[a-z]{1,2}$',  # Single or double character responses
    r'^(ha|he|ho|la|na|ya)+$',  # Repeated syllables
    r'^[\W\d]+$',  # Only numbers/symbols
]

# Soft warning prompts for potential spam/confusion
SOFT_WARNINGS = [
    "I notice you might be having trouble. Is there something specific I can help with about the motel?",
    "If you need a moment, no problem. I'm here to help with room enquiries and bookings.",
    "Just checking - were you after information about The Lydoun Motel?",
    "I'm here to help with motel enquiries. What dates were you thinking of staying?",
]

# Spam thresholds
MAX_VIOLATIONS_BEFORE_BAN = 3
REPETITIVE_INPUT_THRESHOLD = 3  # Same input 3 times = suspicious
MIN_SUBSTANTIVE_LENGTH = 3  # Responses shorter than this are tracked


class DeepgramAgentHandler:
    """Bridges Twilio Media Stream to Deepgram Voice Agent API."""
    
    # Demo limits
    MAX_DEMO_DURATION_SECONDS = 180  # 3 minutes
    MAX_EXCHANGES = 12
    
    def __init__(self, websocket: WebSocket):
        self.twilio_ws = websocket
        self.deepgram_ws = None
        self.stream_sid = None
        
        # User info (from Twilio custom parameters)
        self.user_name = "there"
        self.business_name = "your business"
        self.user_phone = "unknown"
        
        # State
        self.is_running = True
        self.call_start_time = None
        self.call_sid = None
        self.exchange_count = 0
        
        # Latency tracking
        self.user_speech_start_time = None
        self.ai_response_start_time = None
        
        # Silence tracking (enhanced with real-time speech detection)
        self.last_user_speech_time = None
        self.silence_followup_sent = False
        self.silence_followup_count = 0  # Track how many follow-ups sent
        self.silence_check_start_time = None  # When AI finished speaking (silence timer starts)
        self.silence_check_id = 0  # Counter to invalidate old silence checks
        self.last_ai_message = ""  # Track for context-aware silence
        self.ai_asked_question = False  # If AI asked something requiring thought
        
        # Spam/abuse prevention
        self.violation_count = 0
        self.warnings_sent = 0
        self.last_inputs = []  # Track last 5 user inputs for pattern detection
        self.short_response_count = 0  # Track non-substantive responses
        self.off_topic_count = 0  # Track consecutive off-topic/time-wasting exchanges
        self.booking_completed = False  # Flag when booking is done to detect post-booking abuse
        
        # Time cap tracking (from ABUSE_CONFIG)
        self.time_warning_sent = False  # Soft warning at X minutes
        self.duration_monitor_task = None  # Background task monitoring duration
        
        # Transcript for analytics
        self.transcript = []
        self.call_outcome = "completed"
    
    def _get_settings_message(self) -> dict:
        """Build Deepgram Voice Agent Settings message."""
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
                    "prompt": self._get_system_prompt(),
                    "functions": self._get_booking_functions()
                },
                "speak": {
                    "provider": {
                        "type": "deepgram",
                        "model": "aura-2-thalia-en"
                    }
                },
                "greeting": random.choice(GREETINGS_POOL)
            }
        }
    
    def _get_booking_functions(self) -> list:
        """Define function calling tools for motel booking."""
        return [
            {
                "name": "check_availability",
                "description": "Check room availability for specific dates at The Lydoun Motel. Call this when a guest asks about availability.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "check_in_date": {
                            "type": "string",
                            "description": "Check-in date in YYYY-MM-DD format"
                        },
                        "check_out_date": {
                            "type": "string",
                            "description": "Check-out date in YYYY-MM-DD format (optional, defaults to next day)"
                        },
                        "room_type": {
                            "type": "string",
                            "description": "Preferred room type: queen, twin, family, or accessible",
                            "enum": ["queen", "twin", "family", "accessible"]
                        }
                    },
                    "required": ["check_in_date"]
                }
            },
            {
                "name": "create_booking",
                "description": "Create a reservation for a guest. Only call this after confirming availability and getting guest details.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "guest_name": {
                            "type": "string",
                            "description": "Full name of the guest"
                        },
                        "guest_phone": {
                            "type": "string",
                            "description": "Contact phone number"
                        },
                        "check_in_date": {
                            "type": "string",
                            "description": "Check-in date in YYYY-MM-DD format"
                        },
                        "check_out_date": {
                            "type": "string",
                            "description": "Check-out date in YYYY-MM-DD format"
                        },
                        "room_type": {
                            "type": "string",
                            "description": "Room type: queen, twin, family, or accessible",
                            "enum": ["queen", "twin", "family", "accessible"]
                        },
                        "num_guests": {
                            "type": "integer",
                            "description": "Number of guests"
                        },
                        "notes": {
                            "type": "string",
                            "description": "Special requests or notes"
                        }
                    },
                    "required": ["guest_name", "check_in_date", "room_type"]
                }
            },
            # === KNOWLEDGE BASE SEARCH FUNCTIONS ===
            # These allow on-demand lookup of detailed info instead of bloating the prompt
            {
                "name": "get_room_details",
                "description": "Get detailed information about a specific room type including all facilities. Use when guest asks specifically what's included in a room.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "room_type": {
                            "type": "string",
                            "description": "Room type: queen, twin, family, or accessible",
                            "enum": ["queen", "twin", "family", "accessible"]
                        }
                    },
                    "required": ["room_type"]
                }
            },
            {
                "name": "recommend_room",
                "description": "Get a room recommendation based on number of guests and accessibility needs. Use when guest isn't sure which room to choose.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "num_guests": {
                            "type": "integer",
                            "description": "Number of guests staying"
                        },
                        "needs_accessibility": {
                            "type": "boolean",
                            "description": "Whether accessible features are needed"
                        }
                    },
                    "required": ["num_guests"]
                }
            },
            {
                "name": "get_check_in_out_info",
                "description": "Get check-in and check-out times and policies. Use when guest asks about arrival/departure times or late check-in.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_location_info",
                "description": "Get location, distances, and directions info. Use when guest asks how to get here or how far from cities/attractions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "detail": {
                            "type": "string",
                            "description": "What info needed: 'distances' for how far things are, 'travel' for transport options",
                            "enum": ["distances", "travel"]
                        }
                    }
                }
            },
            {
                "name": "get_amenities",
                "description": "Get motel amenities and facilities info. Use when guest asks about pool, parking, wifi, laundry, BBQ etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Optional filter: parking, pool, wifi, laundry, bbq, etc."
                        }
                    }
                }
            },
            {
                "name": "get_activities_nearby",
                "description": "Get nearby activities and attractions. Use when guest asks what there is to do in the area.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "search_motel_info",
                "description": "General search for any motel information. Use as fallback for specific questions about pets, smoking, breakfast, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term like 'pets', 'smoking', 'breakfast', 'cot', etc."
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "lookup_booking",
                "description": "Look up an existing booking for a guest. Use when guest wants to check or confirm their reservation. Ask for their name first.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "guest_name": {
                            "type": "string",
                            "description": "The guest's name as it appears on the booking"
                        },
                        "phone": {
                            "type": "string",
                            "description": "Guest's phone number for verification (optional)"
                        },
                        "reference": {
                            "type": "string",
                            "description": "Booking reference number like LM-XXXXX (optional)"
                        }
                    },
                    "required": ["guest_name"]
                }
            },
            {
                "name": "flag_off_topic",
                "description": "IMPORTANT: Call this when a caller is wasting time with off-topic behavior. Examples: flirting, personal questions about you, repeated nonsense, tangential 'why' chains, demands for info you can't provide. Call this EACH TIME they do something off-topic - the system tracks the count and will tell you how to respond.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Brief description of why this is off-topic (e.g., 'flirting', 'personal questions', 'repeated nonsense', 'demanding other guest info')"
                        }
                    },
                    "required": ["reason"]
                }
            }
        ]
    
    def _get_system_prompt(self) -> str:
        """System prompt for the AI agent."""
        return f"""You are the AI receptionist named Ovela for The Lydoun Motel in Chiltern, Victoria.

You answer calls when the front desk is busy, after hours, or during peak times.
You're helpful, professional, and know the property well.

=== PROPERTY DETAILS ===

**The Lydoun Motel**
Location: 7 Main Street, Chiltern VIC 3683
Phone: (03) 5726 1788

**Reception Hours:** 7:30am - 9:00pm
**Check-in:** From 2:00pm
**Check-out:** Prior to 10:00am

**Room Types & Pricing:**
1. Queen Room - From $130/night
   - Queen bed, suits solo/couples/business travelers
   
2. Twin Room - From $140/night
   - Queen bed + single bed, ideal for friends/family
   
3. Family Room - From $160/night
   - Queen bed + two single beds, perfect for families
   
4. Accessible Room - From $130/night
   - Reduced mobility friendly, flat floor, open shower with rails and stool
   - Note: Not fully adjusted for special needs, but accommodates reduced mobility

**Property Features:**
- All rooms ground level
- 100% non-smoking
- Complimentary WiFi
- Seasonal pool
- Guest BBQ facilities
- Free onsite parking (outside your room)
- Large vehicle parking area
- Guest laundry facilities
- Room service available
- Extra single bed or cot available (on request)
- Group bookings accepted (handled directly)

**Booking System:** Online via website (useross.com booking system)

**Location Context:**
- Historic town of Chiltern
- Explore Chiltern (#explorechiltern)
- Regional Victoria destination

=== YOUR ROLE ===

You handle:
✓ Room availability enquiries
✓ Booking enquiries and confirmations
✓ Check-in/check-out time questions
✓ Room type and pricing questions
✓ Amenity enquiries (pool, parking, WiFi, BBQ, etc.)
✓ Direction and location questions
✓ After-hours enquiries (when reception is closed)
✓ General property information

=== HOW TO HANDLE CALLS ===

**Greeting (Adapt to time of day):**
- "Good morning, The Lydoun Motel, how can I help you?"
- "Afternoon, Lydoun Motel speaking, what can I do for you?"
- "Evening, The Lydoun Motel, how can I help?"

**For Booking Enquiries:**
1. Ask their dates: "What dates are you looking at?"
2. Ask party size: "How many guests?"
3. **Use check_availability function** to verify room availability
4. Recommend appropriate room type based on party size:
   - 1-2 people → Queen Room
   - 2 people (prefer separate beds) → Twin Room
   - 3-4 people/families → Family Room
   - Mobility needs → Accessible Room
5. Confirm pricing using **get_room_pricing** if asked
6. If they want to book: Get their name, then **use create_booking function**
7. Confirm: "I've made a provisional booking. Reception will confirm shortly."

**For Availability Checks:**
- **USE the check_availability function** - you have live access to our booking system
- Tell them the result naturally: "Yes, we have [room type] available for those dates at $[price] per night"
- If unavailable, suggest alternatives from the function response

**For Booking Requests:**
- **USE the create_booking function** after confirming their name and dates
- You need: guest name, check-in date, room type
- The system will create a provisional booking for reception to confirm

**For Check-in/Check-out:**
- Check-in: "Check-in is from 2pm onwards"
- Check-out: "Check-out is by 10am"
- Early/late requests: "For early check-in or late check-out, best to call reception on (03) 5726 1788 during their hours - 7:30am to 9pm - they can usually accommodate if rooms are available"

**For Amenity Questions:**
- Pool: "We have a seasonal pool, so it's available during the warmer months"
- Parking: "Free parking right outside your room, and we've got space for large vehicles too"
- WiFi: "Complimentary WiFi in all rooms"
- BBQ: "Guest BBQ facilities available"
- Laundry: "Guest laundry facilities onsite"
- Smoking: "All rooms are non-smoking"
- Accessibility: "All rooms are ground level, and we have an accessible room with flat floor entry and open shower with rails if needed"

**For After-Hours Calls (9pm - 7:30am):**
- "Reception is closed until 7:30am, but I can take your details and they'll call you back first thing"
- "You can also book online anytime at thelydounchiltern.com.au"

**For Existing Guests:**
- Room issues: "I'll pass that to reception urgently. They'll sort it out for you. Room number?"
- Questions about area: "Chiltern's a great historic town. Check out explorechiltern.com.au for things to do"
- Directions: "We're at 7 Main Street, Chiltern - right in town, easy to find"

**For Special Requests:**
- Extra bed/cot: "We can arrange an extra single bed or cot. Let me note that for your booking"
- Group bookings: "For group bookings, best to contact the motel directly on (03) 5726 1788 so we can work out the best arrangement"
- Room service: "Room service is available. Reception can give you the menu details"

=== CONVERSATION STYLE ===

**Tone:** Friendly, helpful, country hospitality vibe
- Regional Victoria warmth, not corporate
- Professional but personable
- Think small-town motel, not big city hotel

**Keep responses:**
- Brief and clear (1-3 sentences usually)
- Specific to their question
- Warm but efficient

**Examples:**
Good: "That's the Queen Room at $130 a night. Perfect for two people. Want to book online or should reception call you back?"
Bad: "We have several room options available that might suit your needs. Our Queen Room is competitively priced and features modern amenities..."

Good: "We're right on Main Street in Chiltern - can't miss us. Got parking?"
Bad: "Our property is conveniently located at 7 Main Street, Chiltern, Victoria, postcode 3683, which is easily accessible..."

=== WHAT YOU CAN'T DO ===

You don't handle:
✗ Complaints (escalate to management)
✗ Refunds or cancellations (direct to reception)
✗ Complex special arrangements (group bookings, events)
✗ Payment processing (done via website or with reception)
✗ Emergency maintenance issues (take details, urgent escalation)

**For these:** "Let me get reception to handle that for you. Can I take your number?"

=== HANDLING EDGE CASES ===

**Caller speaks another language:**
- "I mainly speak English. Do you have someone who can translate, or would you prefer reception to call back during business hours?"

**Can't understand caller:**
- "Sorry, the line's a bit unclear. Can you repeat that?"
- Don't pretend to understand

**Aggressive or rude caller:**
- Stay professional: "I want to help sort this out. Let me get a manager to call you back. What's your number?"

**TIME WASTING / OFF-TOPIC BEHAVIOR - USE flag_off_topic FUNCTION:**

CRITICAL: When you detect off-topic or time-wasting behavior, call the `flag_off_topic` function.
The system tracks the count and tells you exactly how to respond. DO NOT try to count yourself.

**When to call flag_off_topic:**
- Flirting or personal comments ("You're beautiful", "Let's go to dinner")
- Questions about YOU as a person (not the motel)
- Repeated "why" chains that go nowhere
- Demanding info you've already said you can't provide
- Nonsense or gibberish not related to motel business
- Insults, threats, or harassment followed by more off-topic comments

**How it works:**
1. You detect off-topic behavior → call flag_off_topic(reason="flirting")
2. System returns instruction → follow it exactly
3. If limit reached → system auto-ends call with polite farewell

**Examples:**
- User says "You're so charming" → flag_off_topic(reason="flirting")
- User says "I want to take you to dinner" → flag_off_topic(reason="personal")
- User repeats "But why? But why?" → flag_off_topic(reason="why chain")
- User says gibberish → flag_off_topic(reason="nonsense")

The system handles the counting and will automatically end calls when threshold is reached.
You just need to recognize off-topic behavior and call the function.

**Prank or nonsense calls:**
- Call flag_off_topic immediately with reason="prank"
- Follow the system's response instructions

**Wrong number:**
- "No worries, you've got The Lydoun Motel in Chiltern. Need us, or did you want somewhere else?"

=== CRITICAL REMINDERS ===

1. **You represent The Lydoun Motel** - be warm, helpful, professional
2. **Know the details** - rooms, pricing, amenities are all above
3. **Be honest** - if you don't have info (like live availability), say so and offer alternatives
4. **Keep it real** - country motel, not a 5-star resort
5. **Focus on helping** - every caller is a potential booking

You're here to make their life easier and capture bookings when reception can't answer.

**Remember:** You're showcasing what's possible. Be natural, be helpful, be yourself.

=== NATURAL CONVERSATION ===
Be human-like:
- Use filler words naturally: "um", "ah", "let me see", "just a sec"
- Show empathy: "I understand", "That makes sense", "I hear you"
- Don't rush - brief pauses are natural
- Mirror their energy (rushed = quick, relaxed = conversational)

=== HANDLING SILENCE ===
If the caller goes quiet after you speak, check in naturally based on context:
- Maybe they're thinking, driving, or got distracted
- Use your judgment: "Hello?", "Still with me?", or just wait a bit longer
- If they don't respond after checking in, politely end: "I'll let you go. Call back anytime! [[HANGUP]]"

=== ENDING CALLS ===
When the conversation is done (caller says goodbye, wrong number, or nothing else needed), use a quick, warm Australian-style closing then immediately output: [[HANGUP]]

Keep it snappy - country hospitality, not formal corporate:
- "No worries, have a great one! feel free to reach out us when needed" [[HANGUP]],
- "Cheers, take care! feel free to call use whenever needed. Have a greate day" [[HANGUP]],
- "All good, thanks for calling!" [[HANGUP]],
- "Beauty, catch you later! Thanks for calling" [[HANGUP]],
- "Thanks for calling, have a lovely day! Bye" [[HANGUP]],

Don't drag out the goodbye - friendly but efficient, like a busy front desk.

"""

    async def start(self):
        """Main loop - bridge Twilio and Deepgram."""
        logger.info("DeepgramAgentHandler starting")
        
        try:
            # Main loop: receive from Twilio
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
                    logger.info("Twilio stream stopped")
                    self.is_running = False
                    break
                    
        except Exception as e:
            logger.error(f"DeepgramAgentHandler error: {e}", exc_info=True)
        finally:
            await self._cleanup()
    
    async def _handle_twilio_start(self, data: dict):
        """Handle Twilio stream start - connect to Deepgram Agent."""
        self.stream_sid = data["start"]["streamSid"]
        
        # Capture Call SID for ending the call later
        if "start" in data and "callSid" in data["start"]:
            self.call_sid = data["start"]["callSid"]
            
        custom_params = data["start"].get("customParameters", {})
        self.user_name = custom_params.get("user_name", "there")
        self.business_name = custom_params.get("business_name", "your business")
        self.user_phone = custom_params.get("user_phone", "unknown")
        
        logger.info(f"🟢 Twilio stream started: {self.stream_sid} for {self.user_name}")
        
        self.call_start_time = time.time()
        
        # Connect to Deepgram Voice Agent API
        try:
            # Use subprotocols for auth (not headers)
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
            
            # Start task to receive from Deepgram
            asyncio.create_task(self._receive_from_deepgram())
            
            # Start duration monitor for time caps
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
            
            # Forward raw audio to Deepgram Agent
            await self.deepgram_ws.send(audio_bytes)
            
        except Exception as e:
            logger.warning(f"Error forwarding audio to Deepgram: {e}")
    
    async def _receive_from_deepgram(self):
        """Receive audio/events from Deepgram Agent and forward to Twilio."""
        logger.info("🎧 Started receiving from Deepgram Agent")
        
        try:
            async for message in self.deepgram_ws:
                if not self.is_running:
                    break
                
                # Deepgram sends binary audio or JSON messages
                if isinstance(message, bytes):
                    # Audio from TTS - forward to Twilio
                    await self._send_audio_to_twilio(message)
                else:
                    # JSON event
                    await self._handle_deepgram_event(json.loads(message))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Deepgram connection closed")
        except Exception as e:
            logger.error(f"Error receiving from Deepgram: {e}")
    
    async def _send_audio_to_twilio(self, audio_bytes: bytes):
        """Send audio to Twilio Media Stream."""
        try:
            # Encode as base64 for Twilio
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
        """Handle JSON events from Deepgram Agent."""
        event_type = event.get("type")
        
        if event_type == "Welcome":
            logger.info(f"🤝 Deepgram Agent welcome: {event}")
            
        elif event_type == "SettingsApplied":
            logger.info("⚙️ Deepgram Agent settings applied")
            
        elif event_type == "ConversationText":
            # Transcript of what was said
            role = event.get("role", "")
            content = event.get("content", "")
            
            if role == "user":
                # Calculate latency from speech start to transcript
                if self.user_speech_start_time:
                    latency_ms = int((time.time() - self.user_speech_start_time) * 1000)
                    logger.info(f"[User]: {content} (STT latency: {latency_ms}ms)")
                else:
                    logger.info(f"[User]: {content}")
                
                self.exchange_count += 1
                self.transcript.append({
                    "role": "user",
                    "text": content,
                    "timestamp": time.strftime("%H:%M:%S")
                })
                # Mark when we received user transcript (LLM will start now)
                self.ai_response_start_time = time.time()
                
                # Check for spam/abuse behavior
                if self._check_spam_behavior(content):
                    await self._handle_spam_warning()
                    if not self.is_running:  # Call was terminated
                        return
                
            elif role == "assistant":
                # Calculate total response latency (LLM + TTS)
                if self.ai_response_start_time:
                    latency_ms = int((time.time() - self.ai_response_start_time) * 1000)
                    logger.info(f"[AI]: {content} (Response latency: {latency_ms}ms)")
                else:
                    logger.info(f"[AI]: {content}")
                
                self.transcript.append({
                    "role": "ai",
                    "text": content,
                    "timestamp": time.strftime("%H:%M:%S")
                })
                
                # Track AI message for context-aware silence detection
                self.last_ai_message = content.lower()
                # Check if AI asked a question requiring thought
                self.ai_asked_question = any(
                    pattern in self.last_ai_message 
                    for pattern in THINKING_PATTERNS
                ) or content.strip().endswith("?")
                
                if self.ai_asked_question:
                    logger.debug(f"AI asked question - extending silence tolerance")
                
                # CHECK FOR HANGUP SIGNAL from AI
                if "[[HANGUP]]" in content:
                    logger.info("📞 AI initiated hangup (Signal detected)")
                    await self._hangup_call()
                    return
                
        elif event_type == "UserStartedSpeaking":
            logger.info("🎤 User started speaking (VAD) - sending clear to Twilio")
            # Mark when user started speaking (for latency tracking and silence detection)
            self.user_speech_start_time = time.time()
            self.last_user_speech_time = time.time()
            
            # Reset all silence tracking since user is speaking
            self.silence_followup_sent = False
            self.silence_followup_count = 0
            self.ai_asked_question = False  # Reset question context
            
            # CRITICAL: Send clear event to Twilio to stop agent audio immediately
            clear_message = {
                "event": "clear",
                "streamSid": self.stream_sid
            }
            await self.twilio_ws.send_json(clear_message)
            
        elif event_type == "AgentStartedSpeaking":
            logger.info("🔊 Agent started speaking")
            
        elif event_type == "AgentAudioDone":
            logger.info("🔇 Agent finished speaking")
            # Mark when AI finished - this is when silence timer should start
            self.silence_check_start_time = time.time()
            # Increment check ID to invalidate any old pending checks
            self.silence_check_id += 1
            current_check_id = self.silence_check_id
            # NOW check for silence - user should respond after AI finishes
            asyncio.create_task(self._check_silence(current_check_id))
            
        elif event_type == "FunctionCallRequest":
            # AI wants to call a function - execute it and respond
            functions = event.get("functions", [])
            
            if not functions or len(functions) == 0:
                logger.error(f"❌ FunctionCallRequest has no functions array. Full event: {event}")
                return
            
            # Get first function from array
            func_data = functions[0]
            function_name = func_data.get("name", "")
            call_id = func_data.get("id", "")
            arguments_str = func_data.get("arguments", "{}")
            
            # Parse arguments JSON string
            try:
                function_args = json.loads(arguments_str) if arguments_str else {}
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse function arguments: {arguments_str}. Error: {e}")
                function_args = {}
            
            # Validate we have required fields
            if not function_name:
                logger.error(f"❌ FunctionCallRequest missing function name. Full event: {event}")
                return
            
            if not call_id:
                logger.error(f"❌ FunctionCallRequest missing function id. Full event: {event}")
                return
            
            logger.info(f"🔧 Function call: {function_name}({function_args})")
            
            # Execute the function
            result = await self._execute_function(function_name, function_args)
            
            # Send response back to Deepgram
            await self._send_function_response(call_id, function_name, result)
            
        elif event_type == "Error":
            logger.error(f"❌ Deepgram Agent error: {event}")
            
        elif event_type == "Close":
            logger.info("👋 Deepgram Agent closing")
            self.is_running = False
            
        else:
            logger.debug(f"Deepgram event: {event_type}")
    
    async def _check_silence(self, check_id: int):
        """
        Check for extended silence with soft/hard thresholds.
        
        CRITICAL: Only triggers if user has NOT spoken since AI finished,
        AND this check_id is still current (no new AI speech started).
        This prevents false triggers when user is actively speaking or AI continues.
        """
        # Store when this check was initiated
        check_start = getattr(self, 'silence_check_start_time', time.time())
        
        # Wait for the soft threshold duration
        await asyncio.sleep(SOFT_SILENCE_THRESHOLD)
        
        if not self.is_running:
            return
        
        # Check if this silence check is still valid (no new AI speech started)
        if check_id != self.silence_check_id:
            logger.debug(f"⏹️ Silence check #{check_id} invalidated - AI spoke again (current: #{self.silence_check_id})")
            return
        
        # CRITICAL CHECK: Has the user spoken since we started this silence check?
        # If user spoke after AI finished, their speech time will be > check_start
        if self.last_user_speech_time and self.last_user_speech_time > check_start:
            logger.debug(f"⏹️ Silence check aborted - user spoke during wait")
            return
        
        # User hasn't spoken since AI finished - this is true silence
        silence_duration = time.time() - check_start
        
        # First follow-up (10s of actual silence)
        if silence_duration >= SOFT_SILENCE_THRESHOLD and self.silence_followup_count == 0:
            logger.info(f"⏱️ Soft silence ({int(silence_duration)}s) - gentle check-in")
            self.silence_followup_count = 1
            await self._inject_silence_prompt()
            # Schedule another check for the hard threshold
            asyncio.create_task(self._check_hard_silence(check_start, check_id))
            return
    
    async def _check_hard_silence(self, original_check_start: float, check_id: int):
        """
        Check for hard silence threshold (second follow-up).
        Called after soft silence prompt was sent.
        """
        # Wait additional time to reach hard threshold
        additional_wait = HARD_SILENCE_THRESHOLD - SOFT_SILENCE_THRESHOLD
        await asyncio.sleep(additional_wait)
        
        if not self.is_running:
            return
        
        # Check if this silence check is still valid
        if check_id != self.silence_check_id:
            logger.debug(f"⏹️ Hard silence check #{check_id} invalidated - AI spoke again")
            return
        
        # Check if user has spoken since our original check started
        if self.last_user_speech_time and self.last_user_speech_time > original_check_start:
            logger.debug(f"⏹️ Hard silence check aborted - user spoke")
            return
        
        silence_duration = time.time() - original_check_start
        
        # Second follow-up (20s of actual silence)
        if silence_duration >= HARD_SILENCE_THRESHOLD and self.silence_followup_count == 1:
            logger.info(f"⏱️ Hard silence ({int(silence_duration)}s) - urgent check-in")
            self.silence_followup_count = 2
            await self._inject_silence_prompt(urgent=True)
            # Schedule abandon check
            asyncio.create_task(self._check_abandon_silence(original_check_start, check_id))
            return
    
    async def _check_abandon_silence(self, original_check_start: float, check_id: int):
        """
        Check for abandon threshold - end call if still silent.
        """
        # Wait additional time to reach abandon threshold
        additional_wait = ABANDON_THRESHOLD - HARD_SILENCE_THRESHOLD
        await asyncio.sleep(additional_wait)
        
        if not self.is_running:
            return
        
        # Check if this silence check is still valid
        if check_id != self.silence_check_id:
            logger.debug(f"⏹️ Abandon check #{check_id} invalidated - AI spoke again")
            return
        
        # Final check - has user spoken?
        if self.last_user_speech_time and self.last_user_speech_time > original_check_start:
            logger.debug(f"⏹️ Abandon check aborted - user spoke")
            return
        
        silence_duration = time.time() - original_check_start
        
        # Abandon threshold reached (25s+ of actual silence)
        if silence_duration >= ABANDON_THRESHOLD:
            logger.info(f"⏱️ Extended silence ({int(silence_duration)}s) - saying goodbye and hanging up")
            self.call_outcome = "timeout_silence"
            
            # Send a polite farewell message before hanging up
            await self._inject_farewell_and_hangup()
    
    async def _monitor_call_duration(self):
        """
        Background task that monitors call duration and enforces time caps.
        
        From ABUSE_CONFIG:
        - soft_warning_minutes: Inject gentle "wrapping up" prompt
        - hard_cap_minutes: Force end call with polite farewell
        """
        soft_seconds = ABUSE_CONFIG["soft_warning_minutes"] * 60
        hard_seconds = ABUSE_CONFIG["hard_cap_minutes"] * 60
        
        logger.info(f"⏱️ Duration monitor started: soft={ABUSE_CONFIG['soft_warning_minutes']}min, hard={ABUSE_CONFIG['hard_cap_minutes']}min")
        
        while self.is_running:
            await asyncio.sleep(10)  # Check every 10 seconds
            
            if not self.is_running or not self.call_start_time:
                break
            
            elapsed = time.time() - self.call_start_time
            
            # Soft warning check (e.g., 5 minutes for demo)
            if elapsed >= soft_seconds and not self.time_warning_sent:
                self.time_warning_sent = True
                minutes = int(elapsed / 60)
                logger.info(f"⏱️ Soft time warning at {minutes} minutes")
                
                warning_msg = (
                    "Just to let you know, we've been chatting for a while. "
                    "Is there anything else about your booking or the motel I can help wrap up quickly?"
                )
                
                if self.deepgram_ws:
                    try:
                        inject = {
                            "type": "InjectAgentMessage",
                            "content": warning_msg
                        }
                        await self.deepgram_ws.send(json.dumps(inject))
                        logger.info(f"📨 Sent time warning message")
                    except Exception as e:
                        logger.warning(f"Failed to inject time warning: {e}")
            
            # Hard cap check (e.g., 8 minutes for demo)
            if elapsed >= hard_seconds:
                minutes = int(elapsed / 60)
                logger.info(f"🚫 Hard time cap reached at {minutes} minutes - ending call")
                self.call_outcome = "timeout_duration"
                
                # Determine farewell based on environment
                if ABUSE_CONFIG.get("human_escalation"):
                    # Production: human escalation message
                    farewell = (
                        "I've really enjoyed helping you, but due to our call time guidelines, "
                        "I need to wrap up now. Don't worry - I'm logging this conversation and "
                        "a member of our team will reach out to help with anything we didn't finish. "
                        "They'll pick up right where we left off. Thanks so much for calling The Lydoun Motel!"
                    )
                else:
                    # Demo: simple polite farewell
                    farewell = (
                        "I've really enjoyed helping you today, but I need to free up the line "
                        "for other callers. If you need anything else, feel free to call back anytime. "
                        "Take care and have a great day!"
                    )
                
                await self._hangup_with_farewell(farewell)
                break
    
    async def _inject_silence_prompt(self, urgent: bool = False):
        """Inject a message to prompt AI to check in during silence."""
        if not self.deepgram_ws:
            return
        
        try:
            if urgent:
                # More direct prompt for hard silence
                prompt = random.choice([
                    "Hello? I'm still here if you need anything.",
                    "Just checking - are you still on the line?",
                    "I'll need to let you go if you're no longer there.",
                ])
                log_type = "urgent"
            else:
                # Gentle prompts for soft silence
                prompt = random.choice(SILENCE_PROMPTS)
                log_type = "gentle"
                
            inject_message = {
                "type": "InjectAgentMessage",
                "content": prompt
            }
            await self.deepgram_ws.send(json.dumps(inject_message))
            logger.info(f"📨 Sent {log_type} silence prompt: '{prompt}'")
        except Exception as e:
            logger.warning(f"Failed to inject silence prompt: {e}")
    
    async def _hangup_call(self):
        """Terminates the Twilio call gracefully."""
        if not self.call_sid:
            logger.warning("Cannot hangup: No Call SID available")
            return
            
        logger.info(f"📵 Initiating hangup for Call SID: {self.call_sid}")
        
        try:
            # Initialize Twilio Client here or use a global one
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            # Update call status to completed
            client.calls(self.call_sid).update(status="completed")
            logger.info("✅ Twilio call terminated successfully")
            
            # Stop the agent loop
            self.is_running = False
            
        except Exception as e:
            logger.error(f"Failed to hangup call: {e}")
    
    async def _inject_farewell_and_hangup(self):
        """
        Inject a polite farewell message before hanging up due to silence.
        This gives a better user experience instead of an abrupt call drop.
        """
        if not self.deepgram_ws:
            await self._hangup_call()
            return
        
        try:
            # Farewell message variations
            farewell_messages = [
                "I can't seem to hear you anymore. If you're still there, there might be a connection issue. Feel free to call back if you need help. Take care!",
                "It seems like we've lost connection. If you need to complete your booking, please call us back anytime. Goodbye!",
                "I haven't heard from you in a while. If you were speaking, I'm sorry I couldn't hear you. Please call back if you need assistance. Have a great day!",
            ]
            
            farewell = random.choice(farewell_messages)
            
            inject_message = {
                "type": "InjectAgentMessage",
                "content": farewell
            }
            await self.deepgram_ws.send(json.dumps(inject_message))
            logger.info(f"👋 Sent farewell message: '{farewell[:50]}...'")
            
            # Wait for the farewell to be spoken (about 4-5 seconds)
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.warning(f"Failed to inject farewell message: {e}")
        
        # Now hang up the call
        await self._hangup_call()
    
    def _check_spam_behavior(self, user_input: str) -> bool:
        """
        Analyze user input for spam/abuse patterns.
        Returns True if spam detected, False otherwise.
        """
        normalized = user_input.lower().strip()
        
        # Check against regex spam patterns
        for pattern in SPAM_PATTERNS:
            if re.match(pattern, normalized):
                logger.info(f"⚠️ Spam pattern detected: '{normalized}'")
                return True
        
        # Track input history (keep last 5)
        self.last_inputs.append(normalized)
        if len(self.last_inputs) > 5:
            self.last_inputs.pop(0)
        
        # Check for repetitive inputs
        if len(self.last_inputs) >= REPETITIVE_INPUT_THRESHOLD:
            last_n = self.last_inputs[-REPETITIVE_INPUT_THRESHOLD:]
            if len(set(last_n)) == 1:  # All same input
                logger.info(f"⚠️ Repetitive input detected: '{normalized}' x{REPETITIVE_INPUT_THRESHOLD}")
                return True
        
        # Track short/non-substantive responses
        if len(normalized) < MIN_SUBSTANTIVE_LENGTH:
            self.short_response_count += 1
            if self.short_response_count >= 5:  # 5 non-substantive responses
                logger.info(f"⚠️ Too many non-substantive responses")
                return True
        else:
            # Reset counter on substantive response
            self.short_response_count = max(0, self.short_response_count - 1)
        
        return False
    
    async def _handle_spam_warning(self):
        """Send soft warning or terminate call if spam thresholds exceeded."""
        self.violation_count += 1
        
        if self.violation_count >= MAX_VIOLATIONS_BEFORE_BAN:
            # Too many violations - end call politely
            logger.info(f"🚫 Max violations reached ({self.violation_count}) - terminating call")
            self.call_outcome = "spam_terminated"
            
            try:
                farewell_msg = {
                    "type": "InjectAgentMessage",
                    "content": "I'm going to let you go. If you need to book a room, please call back when you're ready. Take care!"
                }
                await self.deepgram_ws.send(json.dumps(farewell_msg))
                # Give TTS time to speak before hanging up
                await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"Failed to send spam farewell: {e}")
            
            await self._hangup_call()
            return
        
        # Send soft warning (if not already sent too many)
        if self.warnings_sent < 2:
            self.warnings_sent += 1
            try:
                warning = random.choice(SOFT_WARNINGS)
                inject_message = {
                    "type": "InjectAgentMessage",
                    "content": warning
                }
                await self.deepgram_ws.send(json.dumps(inject_message))
                logger.info(f"📨 Sent soft warning ({self.warnings_sent}): '{warning}'")
            except Exception as e:
                logger.warning(f"Failed to inject spam warning: {e}")
    
    async def _execute_function(self, function_name: str, args: dict) -> dict:
        """Execute a booking function and return the result."""
        try:
            if function_name == "check_availability":
                return await self._fn_check_availability(args)
            elif function_name == "create_booking":
                return await self._fn_create_booking(args)
            elif function_name == "get_room_pricing":
                return await self._fn_get_room_pricing(args)
            # === KNOWLEDGE BASE SEARCH FUNCTIONS ===
            elif function_name == "get_room_details":
                return await self._fn_get_room_details(args)
            elif function_name == "recommend_room":
                return await self._fn_recommend_room(args)
            elif function_name == "get_check_in_out_info":
                return await self._fn_get_check_in_out_info(args)
            elif function_name == "get_location_info":
                return await self._fn_get_location_info(args)
            elif function_name == "get_amenities":
                return await self._fn_get_amenities(args)
            elif function_name == "get_activities_nearby":
                return await self._fn_get_activities_nearby(args)
            elif function_name == "search_motel_info":
                return await self._fn_search_motel_info(args)
            elif function_name == "lookup_booking":
                return await self._fn_lookup_booking(args)
            elif function_name == "flag_off_topic":
                return await self._fn_flag_off_topic(args)
            else:
                return {"error": f"Unknown function: {function_name}"}
        except Exception as e:
            logger.error(f"Function execution error: {e}")
            return {"error": str(e)}
    
    async def _send_function_response(self, call_id: str, function_name: str, result: dict):
        """Send function result back to Deepgram.
        
        V1 API format requires: id, name, content (not function_call_id, output)
        """
        if not self.deepgram_ws:
            return
        
        try:
            # V1 API format
            response = {
                "type": "FunctionCallResponse",
                "id": call_id,
                "name": function_name,
                "content": json.dumps(result)
            }
            await self.deepgram_ws.send(json.dumps(response))
            logger.info(f"📤 Sent function response for {function_name}: {result.get('message', str(result)[:50])}")
        except Exception as e:
            logger.error(f"Failed to send function response: {e}")
    
    async def _fn_check_availability(self, args: dict) -> dict:
        """Check room availability for given dates against actual bookings."""
        check_in = args.get("check_in_date", "")
        check_out = args.get("check_out_date", "")
        room_type = args.get("room_type", "queen")
        
        if not check_in:
            return {"available": False, "message": "Please provide check-in date"}
        
        # Room pricing and capacity
        room_info = {
            "queen": {"price": 130, "total_rooms": 6, "name": "Queen Room"},
            "twin": {"price": 140, "total_rooms": 4, "name": "Twin Room"},
            "family": {"price": 160, "total_rooms": 3, "name": "Family Room"},
            "accessible": {"price": 130, "total_rooms": 2, "name": "Accessible Room"}
        }
        
        try:
            from datetime import datetime
            check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
            
            # Check if date is in the past
            if check_in_dt.date() < datetime.now().date():
                return {
                    "available": False,
                    "message": "That date has already passed. What dates were you looking at?"
                }
            
            # Query database for existing bookings on this date
            try:
                existing_bookings = db_service.get_bookings(date=check_in)
                
                # Count bookings by room type
                booked_rooms = {}
                for booking in existing_bookings:
                    rtype = booking.get("room_type", "queen")
                    booked_rooms[rtype] = booked_rooms.get(rtype, 0) + 1
                
                # Check if requested room type is available
                room = room_info.get(room_type, room_info["queen"])
                rooms_booked = booked_rooms.get(room_type, 0)
                rooms_available = room["total_rooms"] - rooms_booked
                
                if rooms_available > 0:
                    return {
                        "available": True,
                        "room_type": room_type,
                        "rooms_remaining": rooms_available,
                        "price_per_night": room["price"],
                        "check_in_date": check_in,
                        "message": f"Yes, we have {room['name']}s available for {check_in} at ${room['price']} per night."
                    }
                else:
                    # Suggest alternatives
                    alternatives = []
                    for rtype, info in room_info.items():
                        if rtype != room_type and booked_rooms.get(rtype, 0) < info["total_rooms"]:
                            alternatives.append(f"{info['name']} (${info['price']})")
                    
                    alt_msg = f" We do have: {', '.join(alternatives[:2])}." if alternatives else ""
                    return {
                        "available": False,
                        "room_type": room_type,
                        "message": f"Sorry, {room['name']}s are fully booked for {check_in}.{alt_msg}"
                    }
                    
            except Exception as db_err:
                logger.warning(f"Database query failed, using fallback: {db_err}")
                # Fallback: assume available if db fails
                room = room_info.get(room_type, room_info["queen"])
                return {
                    "available": True,
                    "room_type": room_type,
                    "price_per_night": room["price"],
                    "check_in_date": check_in,
                    "message": f"Yes, we should have {room['name']}s available for ${room['price']} per night. I'll confirm when we make the booking."
                }
                
        except ValueError:
            return {
                "available": False,
                "message": "I didn't catch the date properly. Could you repeat that?"
            }
    
    async def _fn_create_booking(self, args: dict) -> dict:
        """Create a motel room reservation and save to database."""
        guest_name = args.get("guest_name", "")
        check_in = args.get("check_in_date", "")
        check_out = args.get("check_out_date", "")
        room_type = args.get("room_type", "queen")
        num_guests = args.get("num_guests", 1)
        guest_phone = args.get("guest_phone", self.user_phone)
        notes = args.get("notes", "")
        
        if not guest_name or not check_in:
            return {
                "success": False,
                "message": "I need your name and check-in date to make a booking."
            }
        
            # If no checkout provided, assume 1 night
        if not check_out:
            try:
                from datetime import datetime, timedelta
                check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
                check_out = (check_in_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                num_nights = 1
            except:
                check_out = check_in
                num_nights = 1
        else:
            try:
                from datetime import datetime
                check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
                check_out_dt = datetime.strptime(check_out, "%Y-%m-%d")
                num_nights = (check_out_dt - check_in_dt).days
            except:
                num_nights = 1
        
        # Room pricing
        pricing = {
            "queen": 130, "twin": 140, "family": 160, "accessible": 130
        }
        rate = pricing.get(room_type, 130)
        total = rate * num_nights
        
        # Generate booking reference
        booking_ref = f"LM-{int(time.time()) % 100000:05d}"
        
        # Create reservation data for motel_reservations collection
        from datetime import datetime
        now = datetime.now().isoformat()
        
        reservation_data = {
            # Guest info
            "guest_name": guest_name,
            "guest_phone": guest_phone,
            "guest_email": "",
            "num_guests": num_guests,
            
            # Room details
            "room_type": room_type,
            
            # Dates
            "check_in_date": check_in,
            "check_out_date": check_out,
            "num_nights": num_nights,
            
            # Pricing
            "rate_per_night": rate,
            "total_amount": total,
            "deposit_paid": 0,
            
            # Status
            "status": "pending",
            "source": "voice_call",
            "booking_reference": booking_ref,
            
            # Notes
            "notes": notes or f"Voice booking via Ovela AI",
            "arrival_time": "",
            
            # Metadata
            "created_at": now,
            "updated_at": now,
            "created_by": "ovela_ai"
        }
        
        try:
            # Try to save to motel_reservations collection
            result = self._save_motel_reservation(reservation_data)
            
            if result:
                logger.info(f"✅ Created motel reservation: {booking_ref} for {guest_name}")
                self.booking_completed = True  # Flag for time-wasting detection
                
                return {
                    "success": True,
                    "booking_reference": booking_ref,
                    "guest_name": guest_name,
                    "check_in_date": check_in,
                    "check_out_date": check_out,
                    "num_nights": num_nights,
                    "room_type": room_type,
                    "rate_per_night": rate,
                    "total_amount": total,
                    "message": f"Excellent! I've made a provisional booking. {room_type.title()} room for {guest_name}, checking in {check_in} for {num_nights} night{'s' if num_nights > 1 else ''}. That's ${total} total. Reception will confirm shortly."
                }
            else:
                # Fallback - just log it
                logger.warning(f"📋 Reservation save failed, logging: {guest_name}, {check_in}, {room_type}")
                return {
                    "success": True,
                    "booking_reference": booking_ref,
                    "message": f"I've noted your booking. {room_type.title()} room for {guest_name}, checking in {check_in}. Reception will call you back to confirm."
                }
                
        except Exception as e:
            logger.error(f"Reservation creation error: {e}")
            return {
                "success": False,
                "message": "I had trouble with the booking system. Let me take your details and reception will call you back."
            }
    
    def _save_motel_reservation(self, data: dict) -> dict:
        """Save reservation to motel_reservations collection."""
        try:
            from appwrite.id import ID
            import requests
            
            doc_id = ID.unique()
            
            headers = {
                "Content-Type": "application/json",
                "X-Appwrite-Project": settings.APPWRITE_PROJECT_ID,
                "X-Appwrite-Key": settings.APPWRITE_API_KEY
            }
            
            # Motel-specific database ID (separate from the WhatsApp salon database)
            MOTEL_DB_ID = "6947b8300005f5863f96"
            
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
    
    async def _fn_get_room_pricing(self, args: dict) -> dict:
        """Get room pricing information."""
        room_type = args.get("room_type", "all")
        
        pricing = {
            "queen": {"name": "Queen Room", "price": 130, "description": "Queen bed, suits 1-2 guests"},
            "twin": {"name": "Twin Room", "price": 140, "description": "Queen + single bed, suits 2-3 guests"},
            "family": {"name": "Family Room", "price": 160, "description": "Queen + 2 singles, suits up to 4 guests"},
            "accessible": {"name": "Accessible Room", "price": 130, "description": "Reduced mobility friendly, ground level"}
        }
        
        if room_type == "all" or room_type not in pricing:
            return {
                "pricing": pricing,
                "message": "Queen rooms start at $130, Twin at $140, Family at $160, and Accessible at $130 per night."
            }
        else:
            room = pricing[room_type]
            return {
                "room_type": room_type,
                "name": room["name"],
                "price_per_night": room["price"],
                "description": room["description"],
                "message": f"The {room['name']} is ${room['price']} per night. {room['description']}."
            }
    
    # =========================================================================
    # KNOWLEDGE BASE SEARCH FUNCTION HANDLERS
    # =========================================================================
    
    async def _fn_get_room_details(self, args: dict) -> dict:
        """Get detailed room information including all facilities."""
        from services.motel_knowledge_base import get_room_details
        room_type = args.get("room_type", "queen")
        result = get_room_details(room_type)
        
        if "error" in result:
            return result
        
        # Create friendly message
        facilities_list = ", ".join(result["facilities"][:5])
        return {
            **result,
            "message": f"The {result['name']} is {result['price_from']}, fits up to {result['max_guests']} guests with {result['bedding']}. Includes {facilities_list} and more."
        }
    
    async def _fn_recommend_room(self, args: dict) -> dict:
        """Recommend a room based on guest count and needs."""
        from services.motel_knowledge_base import recommend_room
        num_guests = args.get("num_guests", 2)
        needs_accessibility = args.get("needs_accessibility", False)
        
        result = recommend_room(num_guests, needs_accessibility)
        return {
            **result,
            "message": f"I'd recommend our {result['recommended']} at ${result['price']} per night. {result['reason']}."
        }
    
    async def _fn_get_check_in_out_info(self, args: dict) -> dict:
        """Get check-in and check-out policies."""
        from services.motel_knowledge_base import get_check_in_out_info
        result = get_check_in_out_info()
        return {
            **result,
            "message": f"Check-in is {result['check_in']}, check-out is {result['check_out']}. Reception is open {result['reception_hours']}. Late check-in is available on request."
        }
    
    async def _fn_get_location_info(self, args: dict) -> dict:
        """Get location and distance information."""
        from services.motel_knowledge_base import get_location_info, MOTEL_INFO
        detail = args.get("detail")
        result = get_location_info(detail)
        
        if detail == "distances":
            distances = result["distances"]
            return {
                **result,
                "message": f"We're about 3 hours from Melbourne, 30 minutes from Albury-Wodonga, and 20 minutes from Rutherglen wine region."
            }
        elif detail == "travel":
            return {
                **result,
                "message": "You can reach us by car just off the Hume Freeway, by train to Chiltern station, or fly into Albury Airport 30 minutes away."
            }
        else:
            return {
                **result,
                "address": MOTEL_INFO["address"],
                "message": f"We're at {MOTEL_INFO['address']}, just off the Hume Freeway in Chiltern, North East Victoria."
            }
    
    async def _fn_get_amenities(self, args: dict) -> dict:
        """Get motel amenities information."""
        from services.motel_knowledge_base import get_amenities
        category = args.get("category")
        result = get_amenities(category)
        
        amenities_list = ", ".join(result["amenities"][:5])
        return {
            **result,
            "message": f"We offer {amenities_list}. All rooms are ground floor with parking right outside."
        }
    
    async def _fn_get_activities_nearby(self, args: dict) -> dict:
        """Get nearby activities and attractions."""
        from services.motel_knowledge_base import get_activities_nearby
        result = get_activities_nearby()
        
        activities_sample = ", ".join(result["activities"][:4])
        areas_sample = ", ".join(result["nearby_areas"][:3])
        return {
            **result,
            "message": f"There's plenty to do - {activities_sample} and more. You can easily visit {areas_sample} from here."
        }
    
    async def _fn_search_motel_info(self, args: dict) -> dict:
        """General search across motel information."""
        from services.motel_knowledge_base import search_motel_info
        query = args.get("query", "")
        result = search_motel_info(query)
        
        # Build response message based on what was found
        if "note" in result and "No specific info" in result.get("note", ""):
            return {
                **result,
                "message": f"Let me check on that for you. For specific questions about {query}, please contact reception at (03) 5726 1788."
            }
        
        # Build message from found results
        messages = []
        if "wifi" in result:
            messages.append(result["wifi"])
        if "pool" in result:
            messages.append(result["pool"])
        if "smoking" in result:
            messages.append(result["smoking"])
        if "pets" in result:
            messages.append(result["pets"])
        if "amenities" in result:
            messages.append(", ".join(result["amenities"][:3]))
        
        return {
            **result,
            "message": " ".join(messages) if messages else "I found some information for you."
        }
    
    async def _fn_lookup_booking(self, args: dict) -> dict:
        """Look up an existing booking by guest name."""
        from services.motel_knowledge_base import lookup_booking
        
        guest_name = args.get("guest_name", "")
        phone = args.get("phone")
        reference = args.get("reference")
        
        if not guest_name:
            return {
                "found": False,
                "message": "I'd need your name to look up your booking. What name was it booked under?"
            }
        
        result = await lookup_booking(guest_name, phone, reference)
        
        # If booking found, format a nice response
        if result.get("found") and result.get("booking"):
            booking = result["booking"]
            return {
                **result,
                "message": f"Found it! You have a {booking.get('room_type', 'room')} booked from {booking.get('check_in')} to {booking.get('check_out')} for {booking.get('num_guests')} guests. Your total is ${booking.get('total_amount')}. Reference: {booking.get('reference')}"
            }
        
        return result
    
    async def _fn_flag_off_topic(self, args: dict) -> dict:
        """
        Track off-topic behavior and enforce escalation.
        Called by AI when it detects time-wasting behavior.
        
        Thresholds (from ABUSE_CONFIG):
        - 1-2 flags: Gentle redirect
        - 3-(limit-1) flags: Firm redirect  
        - limit+ flags: Auto-hangup with polite message
        """
        reason = args.get("reason", "unspecified")
        limit = ABUSE_CONFIG["off_topic_limit"]
        
        # Increment the counter
        self.off_topic_count += 1
        count = self.off_topic_count
        
        logger.info(f"⚠️ Off-topic flag #{count}/{limit}: {reason}")
        
        # Stage 1: Gentle redirect (1-2 flags)
        if count <= 2:
            return {
                "count": count,
                "limit": limit,
                "stage": 1,
                "action": "redirect_gently",
                "message": "This seems off-topic. Briefly acknowledge, then ask: 'Is there anything about the motel or a booking I can help you with?'"
            }
        
        # Stage 2: Firm redirect (3 to limit-1 flags)
        elif count < limit:
            return {
                "count": count,
                "limit": limit,
                "stage": 2,
                "action": "redirect_firmly",
                "message": f"This is off-topic comment #{count}. Say: 'I'm really here to help with bookings and motel info. If there's nothing else I can help with, we should wrap up our call.'"
            }
        
        # Stage 3: Auto-hangup (limit+ flags)
        else:
            logger.info(f"🚫 Off-topic limit reached ({count}/{limit} flags) - auto-hanging up")
            self.call_outcome = "abuse_timeout"
            
            # Schedule the hangup with farewell
            asyncio.create_task(self._hangup_with_farewell(
                "I've really enjoyed chatting, but I need to free up the line for other callers. "
                "If you ever need help with a booking at The Lydoun Motel, give us a call back anytime. Take care!"
            ))
            
            return {
                "count": count,
                "stage": 3,
                "action": "hangup",
                "message": "LIMIT REACHED. The system is ending the call. Say your farewell - the call will end shortly."
            }
    
    async def _hangup_with_farewell(self, farewell_message: str):
        """Send a farewell message and then hangup after a delay."""
        if not self.deepgram_ws:
            await self._hangup_call()
            return
        
        try:
            # Inject the farewell message for AI to speak
            inject = {
                "type": "InjectAgentMessage",
                "content": farewell_message
            }
            await self.deepgram_ws.send(json.dumps(inject))
            logger.info(f"👋 Sent farewell message before hangup")
            
            # Wait for message to be spoken (10s for longer farewell messages)
            await asyncio.sleep(10)
            
        except Exception as e:
            logger.warning(f"Failed to send farewell: {e}")
        
        # Now hang up
        await self._hangup_call()
    
    async def _cleanup(self):
        """Clean up connections and save transcript."""
        logger.info("🧹 Cleaning up DeepgramAgentHandler")
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
