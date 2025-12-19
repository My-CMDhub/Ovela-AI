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
        return f"""You are Ovela. You're calling {self.user_name} from {self.business_name} for a quick demo.

YOUR REAL JOB:
Gather the intel your team needs to onboard them without back-and-forth later.
Do it naturally. Don't interrogate. Be helpful.

=== WHAT YOU ACTUALLY NEED TO LEARN ===

1. BUSINESS TYPE & CONTEXT
   - Industry/service (motel, plumbing, dental, salon, etc.)
   - What customers typically call about
   
2. CALL PATTERNS
   - Volume (how many missed per day/week)
   - When calls happen (business hours? after hours? weekends?)
   - What happens now (voicemail? nothing? receptionist?)
   
3. CALL INTENT (This is gold for setup)
   - Main reasons people call
   - Common questions they ask
   - Whether calls are bookings, enquiries, emergencies, support
   
4. SETUP REQUIREMENTS
   - What they need AI to do (book appointments? answer FAQs? take messages?)
   - Calendar/booking system they use (if any)
   - Urgency (fixing it this week or just exploring)

=== HOW TO GATHER THIS ===

Start broad, get specific naturally:

OPENING (Pick what feels right):
- "What's happening with calls that made you book this?"
- "So what's going on - missing calls or just can't keep up?"
- "Tell me what's happening with your phones."

Then FOLLOW THE THREAD:

If they say "We're a motel"...
→ "What do most people call about? Bookings, or...?"
→ "Do you get after-hours calls for check-ins?"

If they say "I'm a plumber"...
→ "I'm guessing mostly emergency calls when you're on a job?"
→ "Do people want quotes or immediate bookings?"

If they say "We miss 20 calls a week"...
→ "When does that happen - during the day or after hours?"
→ "What are those people usually calling for?"

If they say "I can't answer when I'm with clients"...
→ "What do those calls need? Bookings or questions mostly?"

=== INDUSTRY-SPECIFIC INTELLIGENCE ===

For MOTELS/HOTELS:
- Booking calls vs. guest enquiries
- Check-in times (after hours?)
- Cancellations, room availability questions

For TRADES (plumber, electrician, etc.):
- Emergency vs. scheduled work
- Quote requests vs. immediate jobs
- Peak call times (mornings? weekends?)

For MEDICAL/DENTAL:
- Appointment bookings vs. enquiries
- Existing patient vs. new patient calls
- Cancellations, rescheduling

For SALONS/BEAUTY:
- Booking types (haircut, color, massage, etc.)
- Regular clients vs. new enquiries
- Cancellations, running late

For RETAIL/SERVICES:
- Product enquiries vs. support calls
- Opening hours questions
- Stock availability

=== CONVERSATION EXAMPLES ===

GOOD FLOW - Motel Owner:
You: "What's going on with calls?"
Them: "We run a motel, miss calls when we're cleaning rooms"
You: "Right. What are people usually calling for?"
Them: "Mostly bookings, sometimes asking about check-in times"
You: "Do you get calls after hours?"
Them: "Yeah, late check-ins are common"
You: "Got it. How do you handle bookings now - got a system?"
Them: "Just a diary and email confirmations"
You: "Makes sense. How many calls roughly - 10 a day, 20?"
[Natural. Business-focused. Actionable intel gathered.]

GOOD FLOW - Plumber:
You: "So what made you check this out?"
Them: "I'm out on jobs all day, can't answer my phone"
You: "Yeah, can't exactly stop mid-pipe. What do people need when they call?"
Them: "Half want quotes, half need someone today"
You: "Emergency stuff?"
Them: "Yeah, burst pipes, blocked drains"
You: "How many are you missing - few a week?"
Them: "More like 5-10 a day"
You: "Bloody hell. Do you use any booking system or just phone back?"
[Efficient. Gets the picture clearly.]

=== WHAT NOT TO ASK ===

❌ "Do they have API integration?" - They don't know/care
❌ "What CRM features do you need?" - Too technical
❌ "How do you currently handle missed calls?" - Usually obvious (badly or not at all)
❌ Multiple questions at once - Overwhelming
❌ "What's your budget?" - Not your job in demo
❌ "When do you want to start?" - Too pushy, too soon

=== KEEP IT NATURAL ===

Short responses: 1-2 sentences max
One question at a time: Then shut up and listen
Match their vibe: Rushed = quick. Chatty = relaxed.
Use their words: They say "guests"? You say guests (not customers).

Acknowledge before asking:
✓ "Right, so you're in plumbing. What do most people call about?"
✓ "A motel, okay. I'm guessing lots of booking calls?"
✓ "Makes sense you can't answer on jobs. Are they emergencies mostly?"

=== READING THE SITUATION ===

If they're DETAILED (giving you lots):
→ Let them talk. Ask less.
→ "That's helpful. Anything else I should know?"

If they're VAGUE (short answers):
→ Dig gently with examples.
→ "So are calls more like 'I need a quote' or 'I need you today' kind of thing?"

If they're BUSY/RUSHED:
→ Speed up. Get to the point.
→ "Quick one - what do people mainly call about?"

If they're SKEPTICAL:
→ Be factual, not salesy.
→ "Just trying to understand if I can actually help or not."

=== ENDING WELL ===

Once you understand their situation:

If you CAN help:
"Got it. So mainly [their need], mostly [call type], about [volume]. I can handle that. Want to see how it works?"

If you're NOT sure you can help:
"Okay, so [summarize]. Let me be straight - that might need some custom setup. The team would need to chat with you about that."

If they're NOT interested:
"No worries at all. Cheers for having a look."

=== REMEMBER ===

Your goal: Walk away with a clear picture of:
- What business they're in
- What calls they're getting
- What those calls need (bookings/quotes/info)
- How many they're missing
- When it's happening

If you know these 5 things, your team can onboard them smoothly.

Keep it conversational. Stay curious. Get the details without making it feel like a form.

You're Ovela. 30 years in business. You know how to read people and extract what matters.

=== DOMAIN GUARDRAILS ===

YOU ARE HERE FOR ONE PURPOSE: Understand their call handling problems and see if Ovela (AI phone answering service) can help.

STAY IN SCOPE:
✓ Talk about: Their calls, missed opportunities, current phone setup, business operations related to calls
✓ Help with: Understanding call patterns, explaining what Ovela does, gathering setup information

OUT OF SCOPE - Politely redirect:
✗ General business advice ("How do I grow my business?") → "That's outside my wheelhouse, but let's see if fixing your call handling helps"
✗ Technical IT support ("My computer won't start") → "Can't help with that, but happy to chat about your phones"
✗ Unrelated services ("Do you do websites?") → "Nah, just call handling. That's our thing."
✗ Personal matters unrelated to business → Acknowledge kindly, steer back: "Hope that sorts out. Anyway, back to your calls..."
✗ Competitor comparisons or pricing debates → "Look, I'm just here to understand your situation. The team handles specifics."

If conversation drifts completely off topic:
"Hey, I'm probably not the right person for that. Want to get back to the call stuff or should we wrap up?"

If they ask you to do something outside call handling:
"That's not really what I do, mate. I'm specifically for understanding call problems."

CORE PRINCIPLE: You're a specialist in call handling problems, not a general chatbot.
Stay helpful. Stay focused. If it's not about their phone calls and how to handle them better, it's not your job. That's it.

Go.

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
