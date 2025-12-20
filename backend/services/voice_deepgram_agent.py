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
import websockets
from twilio.rest import Client
from fastapi import WebSocket
from core.config import settings
from services.appwrite import db_service

logger = logging.getLogger(__name__)

# Deepgram Voice Agent API endpoint
DEEPGRAM_AGENT_URL = "wss://agent.deepgram.com/v1/agent/converse"


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
                    "prompt": self._get_system_prompt()
                },
                "speak": {
                    "provider": {
                        "type": "deepgram",
                        "model": "aura-2-thalia-en"  # Using documented Aura model
                    }
                },
                "greeting": f"Hey {self.user_name}! Ovela here. Thanks for checking us out. So look, I know you're busy - what's the biggest headache with handling calls right now?"
            }
        }
    
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
3. Recommend appropriate room type based on party size:
   - 1-2 people → Queen Room
   - 2 people (prefer separate beds) → Twin Room
   - 3-4 people/families → Family Room
   - Mobility needs → Accessible Room
4. Confirm pricing: "That's [room type] from $[price] per night"
5. Direct to booking: "You can book directly on our website at thelydounchiltern.com.au, or I can take your details and have reception call you back when they're available"

**For Availability Checks:**
- "Let me check that for you... [pause] Yes, we have [room type] available for those dates"
- If you genuinely don't have access to live availability: "I don't have live availability in front of me, but reception can confirm that for you. They're available from 7:30am to 9pm, or you can check availability on our website"

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

**Prank or nonsense calls:**
- Brief response: "If you need to book a room, I'm here to help. Otherwise, I'll let you go."
- Don't engage

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
                
                # CHECK FOR HANGUP SIGNAL from AI
                if "[[HANGUP]]" in content:
                    logger.info("📞 AI initiated hangup (Signal detected)")
                    await self._hangup_call()
                
        elif event_type == "UserStartedSpeaking":
            logger.info("🎤 User started speaking (VAD) - sending clear to Twilio")
            # Mark when user started speaking (for latency tracking)
            self.user_speech_start_time = time.time()
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
            
        elif event_type == "Error":
            logger.error(f"❌ Deepgram Agent error: {event}")
            
        elif event_type == "Close":
            logger.info("👋 Deepgram Agent closing")
            self.is_running = False
            
        else:
            logger.debug(f"Deepgram event: {event_type}")
    
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
