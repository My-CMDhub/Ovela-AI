"""
services/voice_agent/bridges/cartesia_standalone.py
===================================================
Phase 12.2 — Standalone Cartesia Direct TTS WebSocket Bridge.

Connects directly to Cartesia TTS streaming WebSocket API (`api.cartesia.ai/tts/websocket`)
to generate ultra-low latency audio chunks (`mu-law` 8kHz) and supports instant cancellation (`cancel`)
when local VAD or interruption triggers mid-speech.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional, Dict, Any
import sentry_sdk
import websockets

from core.config import settings

try:    # the socket's own open/closed state; see _socket_open()
    from websockets.protocol import State as _WsState
except ImportError:   # pragma: no cover - very old websockets
    _WsState = None

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
        # One reconnect at a time. Two turns (or a turn and its own retry)
        # finding the socket dead together would otherwise both connect, and
        # the loser's socket would be orphaned with the reader on the other.
        self._connect_lock = asyncio.Lock()
        # Set by close(): a socket we closed ourselves is not a drop to report,
        # and must not be reopened by a turn still winding down after stop().
        self._closing = False

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

    def _socket_open(self) -> bool:
        """
        The flag, and the socket's own word where it can give one.

        `is_connected` only changes when something reads or writes the
        socket. Between turns nothing does, so a socket the keepalive found
        dead (or the server closed) still reads as connected, and the next
        turn's first phrase is what discovers it — by being lost.
        """
        if not self.ws or not self.is_connected:
            return False
        state = getattr(self.ws, "state", None)
        if _WsState is not None and isinstance(state, _WsState):
            return state is _WsState.OPEN
        return True

    async def ensure_connected(self, timeout: float = 2.0) -> bool:
        """
        Reopen a dropped socket. One bounded attempt per call; True if the
        socket is usable afterwards.

        Without this a drop was permanent: every later turn ran the model,
        synthesised nothing, and the call carried on in silence. A bridge
        that never connected is left alone — `start()` owns the first
        connection and ends the call when it fails.
        """
        if self._socket_open():
            return True
        if self.ws is None or self._closing:
            return False
        async with self._connect_lock:
            if self._socket_open():
                return True             # another caller reconnected while we waited
            if self._closing:
                return False
            stale = self.ws
            logger.warning("🟡 [CartesiaStandalone] Socket is down — reconnecting")
            try:
                ok = await asyncio.wait_for(self.connect(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.error(f"🔴 [CartesiaStandalone] Reconnect timed out after {timeout:.1f}s")
                ok = False
            if stale is not None and stale is not self.ws:
                try:
                    await asyncio.wait_for(stale.close(), timeout=1.0)
                except Exception:
                    pass
            if ok and self._closing:
                # stop() ran while we were connecting; this socket is ours to close.
                await self.close()
                return False
            if ok:
                sentry_sdk.capture_message("Cartesia TTS socket reconnected mid-call", level="warning")
            return ok

    def _report_drop(self, reason: str) -> None:
        """A dead TTS socket means a mute agent. It was logged at INFO."""
        self.is_connected = False
        if self._closing:
            return
        logger.error(f"🔴 [CartesiaStandalone] TTS socket dropped mid-call: {reason}")
        sentry_sdk.capture_message(f"Cartesia TTS socket dropped: {reason}", level="error")

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
            # Said out loud: this return is where a dead socket used to turn
            # into a silent call with nothing in the logs. Length only — the
            # words are the caller's business.
            logger.warning(
                f"🟡 [CartesiaStandalone] Dropping {len(transcript)} chars for "
                f"{context_id}: socket is not connected"
            )
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
        # The socket this reader is bound to. ensure_connected() may replace
        # self.ws while a stale reader is still parked on the old one; when the
        # old socket then closes, that reader must not mark the NEW, open
        # socket dead — which silently muted the re-synthesis it opened for.
        ws = self.ws

        def drop(reason: str) -> None:
            if self.ws is ws:
                self._report_drop(reason)
            else:
                logger.debug(f"[CartesiaStandalone] stale reader ended on a replaced socket: {reason}")

        try:
            async for message in ws:
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        yield data
                    except json.JSONDecodeError:
                        logger.warning(f"🟡 [CartesiaStandalone] Malformed JSON: {message[:100]}")
            # Only reached when the socket itself ran out — a clean close from
            # the far end (`async for` swallows ConnectionClosedOK). A caller
            # breaking out raises GeneratorExit at the yield and never gets
            # here, so this does not repeat the mistake noted below.
            drop("closed cleanly by the server")
        except websockets.exceptions.ConnectionClosed as e:
            drop(f"connection closed ({e})")
        except Exception as e:
            drop(f"error receiving audio events: {e}")
        # NO `finally: is_connected = False` — callers break out of this
        # generator on `done`/barge-in every turn. Finalizing the async
        # generator would then mark a perfectly healthy socket as dead, and
        # send_transcript_chunk() would silently no-op for the rest of the call.

    async def close(self) -> None:
        """
        Gracefully close the Cartesia WebSocket connection.
        """
        self._closing = True
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.is_connected = False
        logger.info("🛑 [CartesiaStandalone] Bridge closed")
