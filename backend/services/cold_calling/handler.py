import json
import logging
import asyncio
import base64
import websockets
from fastapi import WebSocket
from typing import Optional

from core.config import settings
from services.cold_calling.prompts import get_prompt
from services.cold_calling.service import call_manager

# Reusing simplified constants or duplicating to ensure isolation
DEEPGRAM_AGENT_URL = "wss://agent.deepgram.com/v1/agent/converse"
CARTESIA_VOICE_ID = "a167e0f3-df7e-4d52-a9c3-f949145efdab"  # Officer Steve Voice

logger = logging.getLogger(__name__)

class ColdCallHandler:
    """
    Simplified Voice Agent Handler for Cold Calling.
    """
    def __init__(self, websocket: WebSocket):
        self.twilio_ws = websocket
        self.deepgram_ws = None
        self.stream_sid = None
        self.call_sid = None
        
        # Metadata
        self.business_name = "Business"
        self.pms = "PMS"
        
        self.is_running = True
        
        # OUTBOUND AUDIO STREAMING QUEUE
        # Instead of sending bursts, we queue audio and send at a steady rate
        self._outbound_queue: asyncio.Queue = asyncio.Queue()
        self._outbound_sender_task = None
        self._send_interval = 0.2  # Send to observer every 200ms
        
    async def start(self):
        logger.info("🚀 ColdCallHandler starting")
        try:
            async for message in self.twilio_ws.iter_text():
                if not self.is_running:
                    break
                
                data = json.loads(message)
                event = data.get("event")
                
                if event == "start":
                    await self._handle_start(data)
                elif event == "media":
                    await self._handle_media(data)
                elif event == "stop":
                    logger.info("📴 Twilio stream stopped")
                    self.is_running = False
                    break
        except Exception as e:
            logger.error(f"ColdCallHandler error: {e}")
        finally:
            await self._cleanup()

    async def _cleanup(self):
        self.is_running = False
        
        # Cancel sender task
        if self._outbound_sender_task:
            self._outbound_sender_task.cancel()
            try:
                await self._outbound_sender_task
            except asyncio.CancelledError:
                pass
        
        if self.deepgram_ws:
            await self.deepgram_ws.close()
        if self.call_sid:
            call_manager.cleanup(self.call_sid)

    async def _handle_start(self, data: dict):
        self.stream_sid = data["start"]["streamSid"]
        self.call_sid = data["start"]["callSid"]
        
        custom_params = data["start"].get("customParameters", {})
        self.business_name = custom_params.get("business_name", "Business")
        self.pms = custom_params.get("pms", "PMS")
        self.mode = custom_params.get("mode", "sales") # Extract mode
        self.prank_type = custom_params.get("prank_type", "theft") # Extract prank type
        
        # Register with manager for observer
        await call_manager.register_twilio_stream(self.call_sid, self.twilio_ws)
        
        logger.info(f"🟢 Cold Call Started ({self.mode}): {self.call_sid} -> {self.business_name}")
        
        # Start the outbound audio sender task (steady streaming to observer)
        self._outbound_sender_task = asyncio.create_task(self._outbound_sender())
        
        # Connect to Deepgram
        try:
            self.deepgram_ws = await websockets.connect(
                DEEPGRAM_AGENT_URL,
                subprotocols=["token", settings.DEEPGRAM_API_KEY]
            )
            
            # Send Settings
            settings_msg = self._get_settings()
            await self.deepgram_ws.send(json.dumps(settings_msg))
            
            # Start Receiver Task
            asyncio.create_task(self._receive_from_deepgram())
            
        except Exception as e:
            logger.error(f"Deepgram Connection Failed: {e}")
            self.is_running = False

    async def _handle_media(self, data: dict):
        if not self.deepgram_ws:
            return
            
        payload = data["media"]["payload"]
        
        # 1. Forward to Deepgram (for AI)
        try:
            audio_bytes = base64.b64decode(payload)
            await self.deepgram_ws.send(audio_bytes)
        except Exception as e:
            logger.warning(f"DG Send Error: {e}")
            
        # 2. Broadcast to Observer (User listening)
        # This is the "Human/Customer" audio channel
        if self.call_sid:
            await call_manager.broadcast_audio(self.call_sid, payload, direction="inbound")

    async def _outbound_sender(self):
        """
        Steady-rate sender for outbound audio to observer.
        Prevents blasting by sending accumulated chunks every 200ms.
        """
        buffer = b""
        
        try:
            while self.is_running:
                # Wait for the send interval
                await asyncio.sleep(self._send_interval)
                
                # Collect all available chunks from queue (non-blocking)
                while not self._outbound_queue.empty():
                    try:
                        chunk = self._outbound_queue.get_nowait()
                        buffer += chunk
                    except asyncio.QueueEmpty:
                        break
                
                # Send accumulated buffer if we have data
                if buffer and self.call_sid:
                    payload = base64.b64encode(buffer).decode("utf-8")
                    await call_manager.broadcast_audio(self.call_sid, payload, direction="outbound")
                    buffer = b""
                    
        except asyncio.CancelledError:
            # Flush any remaining buffer on cancellation
            if buffer and self.call_sid:
                payload = base64.b64encode(buffer).decode("utf-8")
                await call_manager.broadcast_audio(self.call_sid, payload, direction="outbound")
            raise

    async def _receive_from_deepgram(self):
        try:
            async for message in self.deepgram_ws:
                if isinstance(message, bytes):
                    # TTS Audio from AI (raw mulaw bytes)
                    
                    # 1. Send to Twilio (User hears AI) - send immediately, Twilio handles its own buffering
                    payload = base64.b64encode(message).decode("utf-8")
                    media_msg = {
                        "event": "media",
                        "streamSid": self.stream_sid,
                        "media": {"payload": payload}
                    }
                    await self.twilio_ws.send_json(media_msg)
                    
                    # 2. Queue for Observer (steady-rate streaming)
                    # The sender task will stream these at a consistent rate
                    await self._outbound_queue.put(message)
                        
                else:
                    # JSON Event
                    event = json.loads(message)
                    event_type = event.get("type")
                    
                    if event_type == "ConversationText":
                        role = event.get("role")
                        content = event.get("content")
                        logger.info(f"🗣️ [{role}]: {content}")
                        
                    elif event_type == "UserStartedSpeaking":
                        # BARGE-IN DETECTED
                        # 1. Clear Twilio Buffer
                        logger.info("🛑 User Interrupted - Clearing Twilio Buffer")
                        clear_msg = {
                            "event": "clear",
                            "streamSid": self.stream_sid,
                        }
                        await self.twilio_ws.send_json(clear_msg)
                        
                        # 2. Clear outbound queue (don't send stale audio)
                        while not self._outbound_queue.empty():
                            try:
                                self._outbound_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                        
                        # 3. Tell Frontend to Clear Outbound Queue
                        if self.call_sid:
                            await call_manager.broadcast_event(self.call_sid, {"event": "clear_audio", "direction": "outbound"})
                            
        except Exception as e:
            logger.error(f"DG Receive Error: {e}")

    def _get_settings(self):
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
                        "model": "nova-3",
                        "endpointing": 350,
                        "smart_format": True
                    }
                },
                "think": {
                    "provider": {
                        "type": "open_ai",
                        "model": "gpt-4.1-mini"
                    },
                    "prompt": get_prompt(self.business_name, self.pms, self.mode, self.prank_type)
                },
                "speak": {
                    "provider": {
                        "type": "cartesia",
                        "model_id": "sonic-3",
                        "voice": {
                            "mode": "id",
                            "id": CARTESIA_VOICE_ID
                        }
                    }
                },
                "greeting": f"Hi, is this {self.business_name}?"
            }
        }
