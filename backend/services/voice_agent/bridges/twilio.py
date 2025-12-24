"""
Twilio Bridge Module.

Handles communication with Twilio Media Streams WebSocket.
"""

import json
import logging
import base64

from twilio.rest import Client
from core.config import settings

logger = logging.getLogger(__name__)


class TwilioBridge:
    """
    Handles Twilio WebSocket communication for voice calls.
    
    Responsibilities:
    - Parse incoming Twilio WebSocket messages
    - Format outgoing audio for Twilio
    - Handle call control (hangup, clear audio)
    """
    
    def __init__(self, websocket):
        self.ws = websocket
        self.stream_sid = None
        self.call_sid = None
        self.user_phone = None
        self.user_name = "Caller"
    
    async def parse_message(self, message: str) -> dict:
        """
        Parse incoming Twilio WebSocket message.
        
        Returns:
            dict with 'event' type and relevant data
        """
        try:
            data = json.loads(message)
            event_type = data.get("event")
            
            if event_type == "start":
                # Extract call metadata
                start_data = data.get("start", {})
                custom_params = start_data.get("customParameters", {})
                
                self.stream_sid = data.get("streamSid")
                self.call_sid = start_data.get("callSid")
                self.user_phone = custom_params.get("caller_phone", "Unknown")
                self.user_name = custom_params.get("caller_name", "Caller")
                
                return {
                    "event": "start",
                    "stream_sid": self.stream_sid,
                    "call_sid": self.call_sid,
                    "user_phone": self.user_phone,
                    "user_name": self.user_name
                }
            
            elif event_type == "media":
                # Extract audio data
                media = data.get("media", {})
                payload = media.get("payload", "")
                return {
                    "event": "media",
                    "audio": base64.b64decode(payload) if payload else None
                }
            
            elif event_type == "stop":
                return {"event": "stop"}
            
            else:
                return {"event": event_type, "data": data}
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Twilio message: {e}")
            return {"event": "error", "error": str(e)}
    
    async def send_audio(self, audio_bytes: bytes):
        """Send audio to Twilio Media Stream."""
        if not audio_bytes or not self.stream_sid:
            return
        
        try:
            message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload": base64.b64encode(audio_bytes).decode("utf-8")
                }
            }
            await self.ws.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send audio to Twilio: {e}")
    
    async def clear_audio(self):
        """Send clear message to stop any queued audio on caller's end."""
        if not self.stream_sid:
            return
        
        try:
            message = {
                "event": "clear",
                "streamSid": self.stream_sid
            }
            await self.ws.send_json(message)
            logger.debug("🔇 Sent clear audio to Twilio")
        except Exception as e:
            logger.warning(f"Failed to send clear to Twilio: {e}")
    
    async def hangup(self):
        """
        Terminate the Twilio call using REST API.
        
        Returns:
            bool: True if hangup succeeded
        """
        if not self.call_sid:
            logger.warning("Cannot hangup - no call SID")
            return False
        
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.calls(self.call_sid).update(status="completed")
            logger.info("✅ Twilio call terminated successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to hangup Twilio call: {e}")
            return False
