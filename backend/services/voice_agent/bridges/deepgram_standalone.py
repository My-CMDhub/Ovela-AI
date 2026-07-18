"""
services/voice_agent/bridges/deepgram_standalone.py
===================================================
Phase 12.2 — Standalone Deepgram Listen (STT / Flux v2) WebSocket Bridge.

Connects directly to Deepgram Listen / Flux v2 streaming API to receive
raw audio packets and emit structured conversational turn events:
- StartOfTurn (SpeechStarted)
- EagerEndOfTurn
- TurnResumed
- EndOfTurn (TurnEnded / SpeechEnded)
- Interim & Final Transcripts
"""

import json
import logging
from typing import AsyncGenerator, Optional, Dict, Any
import websockets

from core.config import settings

logger = logging.getLogger(__name__)


class DeepgramStandaloneBridge:
    """
    Standalone WebSocket bridge for Deepgram Listen / Flux v2 conversational API.
    """
    def __init__(
        self,
        sample_rate: int = 8000,
        model: str = "flux",
        version: str = "v2",
        encoding: str = "mulaw",
        channels: int = 1,
    ):
        self.sample_rate = sample_rate
        self.model = model
        self.version = version
        self.encoding = encoding
        self.channels = channels
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False

    @property
    def url(self) -> str:
        """
        Constructs the query-parameterized Deepgram streaming URL.
        """
        params = [
            f"model={self.model}",
            f"version={self.version}",
            f"encoding={self.encoding}",
            f"sample_rate={self.sample_rate}",
            f"channels={self.channels}",
            "interim_results=true",
            "smart_format=true",
        ]
        return f"wss://api.deepgram.com/v1/listen?{'&'.join(params)}"

    async def connect(self) -> bool:
        """
        Establish WebSocket connection to Deepgram Listen API.
        """
        try:
            extra_headers = {"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"}
            self.ws = await websockets.connect(
                self.url,
                extra_headers=extra_headers,
                ping_interval=5,
                ping_timeout=20,
            )
            self.is_connected = True
            logger.info("🟢 [DeepgramStandalone] Connected to Deepgram Listen / Flux v2")
            return True
        except Exception as e:
            logger.error(f"🔴 [DeepgramStandalone] Connection failed: {e}")
            self.is_connected = False
            return False

    async def send_audio(self, audio_bytes: bytes) -> None:
        """
        Send raw telephony mu-law/PCM audio payload to Deepgram WebSocket.
        """
        if not self.ws or not self.is_connected or not audio_bytes:
            return
        try:
            await self.ws.send(audio_bytes)
        except Exception as e:
            logger.warning(f"🟡 [DeepgramStandalone] Failed to send audio packet: {e}")
            self.is_connected = False

    async def send_configure(
        self,
        eot_threshold: float = 0.7,
        eot_timeout_ms: int = 1500,
        eager_eot_threshold: float = 0.5,
    ) -> None:
        """
        Send runtime configuration (Configure message) to adjust turn detection
        or sensitivity parameters on the fly without reconnecting.
        """
        if not self.ws or not self.is_connected:
            return
        payload = {
            "type": "Configure",
            "processors": {
                "interim_results": True,
                "turn_taking": {
                    "eot_threshold": eot_threshold,
                    "eot_timeout_ms": eot_timeout_ms,
                    "eager_eot_threshold": eager_eot_threshold,
                },
            },
        }
        try:
            await self.ws.send(json.dumps(payload))
            logger.info("📤 [DeepgramStandalone] Sent runtime turn configuration")
        except Exception as e:
            logger.error(f"🔴 [DeepgramStandalone] Failed to send Configure: {e}")

    async def send_keep_alive(self) -> None:
        """
        Send KeepAlive message to prevent timeout when assistant is speaking long turns.
        """
        if not self.ws or not self.is_connected:
            return
        try:
            await self.ws.send(json.dumps({"type": "KeepAlive"}))
        except Exception as e:
            logger.warning(f"🟡 [DeepgramStandalone] Failed to send KeepAlive: {e}")

    async def receive_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yield parsed JSON conversational events and transcripts from Deepgram.
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
                        logger.warning(f"🟡 [DeepgramStandalone] Malformed JSON received: {message[:100]}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 [DeepgramStandalone] Connection closed by server")
        except Exception as e:
            logger.error(f"🔴 [DeepgramStandalone] Error receiving stream events: {e}")
        finally:
            self.is_connected = False

    async def close(self) -> None:
        """
        Gracefully close the Deepgram WebSocket connection.
        """
        if self.ws:
            try:
                # Send empty binary packet or close frame per Deepgram spec
                await self.ws.send(b"")
                await self.ws.close()
            except Exception:
                pass
        self.is_connected = False
        logger.info("🛑 [DeepgramStandalone] Bridge closed")
