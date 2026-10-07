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
        model: str = "flux-general-en",
        version: str = "",
        encoding: str = "mulaw",
        channels: int = 1,
        eot_threshold: float = 0.6,
        eager_eot_threshold: Optional[float] = 0.4,
        eot_timeout_ms: int = 1000,
    ):
        self.sample_rate = sample_rate
        self.model = model
        self.version = version
        self.encoding = encoding
        self.channels = channels
        self.eot_threshold = eot_threshold
        self.eager_eot_threshold = eager_eot_threshold
        self.eot_timeout_ms = eot_timeout_ms
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False

    @property
    def url(self) -> str:
        """
        Constructs the query-parameterized Deepgram streaming URL.
        Routely uses /v2/listen for Flux models and /v1/listen for legacy models.
        """
        is_flux = self.model.startswith("flux")
        endpoint = "v2" if is_flux else "v1"

        params = [
            f"model={self.model}",
            f"encoding={self.encoding}",
            f"sample_rate={self.sample_rate}",
        ]

        if is_flux:
            if self.eot_threshold is not None:
                params.append(f"eot_threshold={self.eot_threshold}")
            if self.eager_eot_threshold is not None:
                params.append(f"eager_eot_threshold={self.eager_eot_threshold}")
            if self.eot_timeout_ms is not None:
                params.append(f"eot_timeout_ms={self.eot_timeout_ms}")
        else:
            params.append(f"channels={self.channels}")
            params.append("interim_results=true")
            params.append("smart_format=true")
            if self.version:
                params.append(f"version={self.version}")

        return f"wss://api.deepgram.com/{endpoint}/listen?{'&'.join(params)}"

    async def connect(self) -> bool:
        """
        Establish WebSocket connection to Deepgram Listen API.
        """
        try:
            headers = {"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"}
            try:
                self.ws = await websockets.connect(
                    self.url,
                    additional_headers=headers,
                    ping_interval=5,
                    ping_timeout=20,
                )
            except TypeError:
                self.ws = await websockets.connect(
                    self.url,
                    extra_headers=headers,
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
        # Must match the constructor/connect-URL defaults above, or an
        # argument-less call silently retunes turn-taking mid-call.
        eot_threshold: float = 0.6,
        eot_timeout_ms: int = 1000,
        eager_eot_threshold: float = 0.4,
    ) -> None:
        """
        Send runtime configuration (Configure message) to adjust turn detection
        or sensitivity parameters on the fly without reconnecting.
        """
        if not self.ws or not self.is_connected:
            return
        # Flux v2 schema is `thresholds`; the old Listen v1 `processors` shape is
        # rejected with ConfigureFailure and the stream then yields nothing.
        payload = {
            "type": "Configure",
            "thresholds": {
                "eot_threshold": eot_threshold,
                "eot_timeout_ms": eot_timeout_ms,
                "eager_eot_threshold": eager_eot_threshold,
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
            self.is_connected = False
        except Exception as e:
            logger.error(f"🔴 [DeepgramStandalone] Error receiving stream events: {e}")
            self.is_connected = False
        # Deliberately no `finally` — see cartesia_standalone.receive_audio_events().
        # Finalizing this generator must not mark a live socket as disconnected.

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
