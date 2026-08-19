"""
services/voice_agent/bridges/cartesia_standalone.py
===================================================
Phase 12.2 — Standalone Cartesia Direct TTS WebSocket Bridge.

Connects directly to Cartesia TTS streaming WebSocket API (`api.cartesia.ai/tts/websocket`)
to generate ultra-low latency audio chunks (`mu-law` 8kHz) and supports instant cancellation (`cancel`)
when local VAD or interruption triggers mid-speech.
"""

import json
import logging
from typing import AsyncGenerator, Optional, Dict, Any
import websockets

from core.config import settings

logger = logging.getLogger(__name__)


class CartesiaStandaloneBridge:
    """
    Standalone WebSocket bridge for Cartesia Direct TTS streaming API.
    """
    def __init__(
        self,
        model_id: str = "sonic-3",
        voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091",
        sample_rate: int = 8000,
        # Cartesia rejects "mulaw" — the raw-container encoding is "pcm_mulaw".
        encoding: str = "pcm_mulaw",
        container: str = "raw",
    ):
        self.model_id = model_id
        self.voice_id = voice_id
        # Optional generation_config overrides, set from tenant voice_settings.
        self.speed: Optional[float] = None
        self.volume: Optional[float] = None
        self.sample_rate = sample_rate
        self.encoding = encoding
        self.container = container
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False

    @property
    def url(self) -> str:
        """
        Constructs the query-parameterized Cartesia WebSocket URL.
        """
        api_key = settings.CARTESIA_API_KEY or ""
        return f"wss://api.cartesia.ai/tts/websocket?api_key={api_key}&cartesia_version=2024-06-10"

    async def connect(self) -> bool:
        """
        Establish WebSocket connection to Cartesia TTS streaming server.
        """
        if not settings.CARTESIA_API_KEY:
            logger.error("🔴 [CartesiaStandalone] CARTESIA_API_KEY not configured")
            return False
        try:
            self.ws = await websockets.connect(
                self.url,
                ping_interval=5,
                ping_timeout=20,
            )
            self.is_connected = True
            logger.info("🟢 [CartesiaStandalone] Connected to Cartesia Direct TTS")
            return True
        except Exception as e:
            logger.error(f"🔴 [CartesiaStandalone] Connection failed: {e}")
            self.is_connected = False
            return False

    async def send_transcript_chunk(
        self,
        context_id: str,
        transcript: str,
        continue_stream: bool = True,
    ) -> None:
        """
        Send a transcript chunk to Cartesia for immediate synthesis.
        """
        if not self.ws or not self.is_connected:
            return
        payload = {
            "context_id": context_id,
            "model_id": self.model_id,
            "transcript": transcript,
            "voice": {
                "mode": "id",
                "id": self.voice_id,
            },
            "output_format": {
                "container": self.container,
                "encoding": self.encoding,
                "sample_rate": self.sample_rate,
            },
            "continue": continue_stream,
        }
        # Cartesia takes numeric speed (0.6-1.5) / volume (0.5-2.0) under
        # generation_config; the top-level slow/normal/fast form is deprecated.
        generation_config = {}
        if self.speed is not None:
            generation_config["speed"] = self.speed
        if self.volume is not None:
            generation_config["volume"] = self.volume
        if generation_config:
            payload["generation_config"] = generation_config
        try:
            await self.ws.send(json.dumps(payload))
        except Exception as e:
            logger.warning(f"🟡 [CartesiaStandalone] Failed to send transcript chunk: {e}")
            self.is_connected = False

    async def cancel_stream(self, context_id: str) -> None:
        """
        Immediately cancel an ongoing TTS generation context when barge-in is detected.
        """
        if not self.ws or not self.is_connected:
            return
        payload = {
            "context_id": context_id,
            "cancel": True,
        }
        try:
            await self.ws.send(json.dumps(payload))
            logger.info(f"🛑 [CartesiaStandalone] Sent cancel for context_id={context_id}")
        except Exception as e:
            logger.warning(f"🟡 [CartesiaStandalone] Failed to send cancel: {e}")

    async def receive_audio_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yield parsed JSON events and base64 audio chunks from Cartesia.
        """
        if not self.ws:
            return
        try:
            async for message in self.ws:
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        yield data
                    except json.JSONDecodeError:
                        logger.warning(f"🟡 [CartesiaStandalone] Malformed JSON: {message[:100]}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 [CartesiaStandalone] Connection closed by server")
            self.is_connected = False
        except Exception as e:
            logger.error(f"🔴 [CartesiaStandalone] Error receiving audio events: {e}")
            self.is_connected = False
        # NO `finally: is_connected = False` — callers break out of this
        # generator on `done`/barge-in every turn. Finalizing the async
        # generator would then mark a perfectly healthy socket as dead, and
        # send_transcript_chunk() would silently no-op for the rest of the call.

    async def close(self) -> None:
        """
        Gracefully close the Cartesia WebSocket connection.
        """
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.is_connected = False
        logger.info("🛑 [CartesiaStandalone] Bridge closed")
