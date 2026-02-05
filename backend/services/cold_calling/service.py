import logging
import json
import base64
import asyncio
from typing import Dict, Optional, Any
import httpx
from fastapi import WebSocket

from core.config import settings

logger = logging.getLogger(__name__)

class CallManager:
    """
    Manages active cold calls and their state.
    Bridges the Twilio Stream (Audio) to the Observer (Frontend).
    """
    def __init__(self):
        # Map call_sid -> State Dict
        # State: { "twilio_ws": WebSocket, "observer_ws": WebSocket, "audio_queue": asyncio.Queue }
        self.active_calls: Dict[str, Dict[str, Any]] = {}

    async def register_observer(self, call_sid: str, ws: WebSocket):
        """Register a frontend observer for a specific call."""
        if call_sid not in self.active_calls:
            self.active_calls[call_sid] = {}
        
        self.active_calls[call_sid]["observer_ws"] = ws
        logger.info(f"Observer joined call {call_sid}")

    async def register_twilio_stream(self, call_sid: str, ws: WebSocket):
        """Register the Twilio Media Stream."""
        if call_sid not in self.active_calls:
            self.active_calls[call_sid] = {}
        
        self.active_calls[call_sid]["twilio_ws"] = ws
        logger.info(f"Twilio stream connected for call {call_sid}")

    async def broadcast_audio(self, call_sid: str, audio_payload: str, direction: str = "inbound"):
        """
        Send audio to the observer.
        audio_payload: Base64 string of mulaw audio.
        direction: 'inbound' (user speaking) or 'outbound' (AI speaking).
        """
        call_state = self.active_calls.get(call_sid)
        if not call_state:
            return

        observer_ws = call_state.get("observer_ws")
        if observer_ws:
            try:
                # We send the raw payload + metadata to frontend
                # Frontend will decode play.
                msg = {
                    "event": "audio",
                    "direction": direction,
                    "media": audio_payload
                }
                await observer_ws.send_json(msg)
            except Exception as e:
                logger.warning(f"Failed to broadcast to observer: {e}")
                # cleanup?
                call_state["observer_ws"] = None

    async def broadcast_event(self, call_sid: str, event_data: dict):
        """
        Broadcast a generic JSON event to observers.
        """
        call_state = self.active_calls.get(call_sid)
        if not call_state:
            return

        observer_ws = call_state.get("observer_ws")
        if observer_ws:
            try:
                await observer_ws.send_json(event_data)
            except Exception as e:
                logger.warning(f"Failed to broadcast event to observer: {e}")
                call_state["observer_ws"] = None

    def cleanup(self, call_sid: str):
        if call_sid in self.active_calls:
            del self.active_calls[call_sid]

call_manager = CallManager()


class ColdCallService:
    @staticmethod
    async def start_call(to_number: str, business_name: str, pms_name: str = "PMS", mode: str = "sales", prank_type: str = "theft") -> str:
        """
        Initiate an outbound call via Twilio API (httpx).
        Returns the Call SID.
        """
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            raise ValueError("Twilio credentials missing")

        # Clean number
        clean_number = to_number.strip().replace(" ", "")
        if clean_number.startswith("0"):
            clean_number = "+61" + clean_number[1:] # default to AU if 0 start
        
        # Domain for callback
        # We need the public URL of the backend. 
        # Since we are local, we assume ngrok or similar is set in settings.
        # IF running purely local without tunnel, Twilio can't reach us.
        # User said "running completely locally". 
        # BUT Twilio needs a public URL.
        # I will assume `settings.API_DOMAIN` or `settings.BASE_URL` is set to something reachable (ngrok).
        # Fallback to a placeholder that user must configure.
        base_url = getattr(settings, "API_DOMAIN", None) or getattr(settings, "BASE_URL", None)
        if not base_url:
             # Try to construct or warn
             # For local dev, we often put the ngrok url in .env
             pass
        
        if not base_url:
            logger.error("No API_DOMAIN/BASE_URL found for Twilio callback")
            # We proceed but it might fail if not absolute url? 
            # Actually Twilio Requires absolute URL.
            # I will use a dummy if not present to avoid crash, but it won't work without it.
            base_url = "https://example.com"

        # TwiML Endpoint
        # We encode extra params in the URL query if needed, or rely on internal DB.
        # We'll encode business name in query params to keep it stateless.
        import urllib.parse
        encoded_business = urllib.parse.quote(business_name)
        encoded_pms = urllib.parse.quote(pms_name)
        encoded_mode = urllib.parse.quote(mode)
        encoded_prank_type = urllib.parse.quote(prank_type)
        
        twiml_url = f"{base_url}/api/cold-calling/twiml/connect?business_name={encoded_business}&pms={encoded_pms}&mode={encoded_mode}&prank_type={encoded_prank_type}"

        auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Calls.json"
        
        data = {
            "To": clean_number,
            "From": "+61348236219",  # Officer Steve's number (Prank Mode)
            "Url": twiml_url,
            "Method": "POST"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, auth=auth)
            if response.status_code >= 400:
                logger.error(f"Twilio Error: {response.text}")
                response.raise_for_status()
            
            resp_data = response.json()
            return resp_data.get("sid")

