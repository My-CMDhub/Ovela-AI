"""
Deepgram Bridge Module.

Handles communication with Deepgram Voice Agent API.
"""

import json
import logging
import websockets

from ..config import DEEPGRAM_AGENT_URL
from core.config import settings

logger = logging.getLogger(__name__)


class DeepgramBridge:
    """
    Handles Deepgram Voice Agent API communication.
    
    Responsibilities:
    - Connect to Deepgram Agent API
    - Send/receive audio and control messages
    - Handle function calls and responses
    """
    
    def __init__(self):
        self.ws = None
        self.is_connected = False
    
    async def connect(self) -> bool:
        """
        Connect to Deepgram Voice Agent API.
        
        Returns:
            bool: True if connection succeeded
        """
        try:
            self.ws = await websockets.connect(
                DEEPGRAM_AGENT_URL,
                subprotocols=["token", settings.DEEPGRAM_API_KEY],
                ping_interval=5,
                ping_timeout=20
            )
            self.is_connected = True
            logger.info("🟢 Connected to Deepgram Voice Agent API")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram Agent: {e}")
            self.is_connected = False
            return False
    
    async def send_settings(self, settings_dict: dict):
        """Send Settings message to configure the agent."""
        if not self.ws:
            return
        
        try:
            await self.ws.send(json.dumps(settings_dict))
            logger.info("📤 Sent Settings to Deepgram Agent")
        except Exception as e:
            logger.error(f"Failed to send settings: {e}")
    
    async def send_audio(self, audio_bytes: bytes):
        """Send audio data to Deepgram Agent."""
        if not self.ws or not audio_bytes:
            return
        
        try:
            await self.ws.send(audio_bytes)
        except Exception as e:
            logger.warning(f"Failed to send audio to Deepgram: {e}")
    
    async def receive(self):
        """
        Receive next message from Deepgram.
        
        Returns:
            bytes or dict depending on message type
        """
        if not self.ws:
            return None
        
        try:
            message = await self.ws.recv()
            
            # Could be binary (audio) or text (JSON event)
            if isinstance(message, bytes):
                return {"type": "audio", "data": message}
            else:
                return json.loads(message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 Deepgram connection closed")
            self.is_connected = False
            return None
        except Exception as e:
            logger.warning(f"Error receiving from Deepgram: {e}")
            return None
    
    async def inject_message(self, content: str):
        """
        Inject a message for the agent to speak.
        
        Args:
            content: Text message for agent to speak
        """
        if not self.ws:
            return
        
        try:
            inject = {
                "type": "InjectAgentMessage",
                "content": content
            }
            await self.ws.send(json.dumps(inject))
            logger.info(f"📨 Injected message: {content[:50]}...")
        except Exception as e:
            logger.warning(f"Failed to inject message: {e}")
    
    async def send_function_response(self, call_id: str, function_name: str, result: dict):
        """
        Send function call response back to Deepgram.
        
        Args:
            call_id: ID of the function call
            function_name: Name of the function called
            result: Function result to send back
        """
        if not self.ws:
            return
        
        try:
            # V1 API format
            response = {
                "type": "FunctionCallResponse",
                "id": call_id,
                "name": function_name,
                "content": json.dumps(result)
            }
            await self.ws.send(json.dumps(response))
            logger.info(f"📤 Sent function response for {function_name}")
        except Exception as e:
            logger.error(f"Failed to send function response: {e}")
    
    async def close(self):
        """Close the Deepgram connection."""
        if self.ws:
            try:
                await self.ws.close()
                logger.info("🔌 Deepgram connection closed")
            except Exception as e:
                logger.warning(f"Error closing Deepgram connection: {e}")
            finally:
                self.ws = None
                self.is_connected = False
