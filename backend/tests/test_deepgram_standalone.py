"""
tests/test_deepgram_standalone.py
===================================
Phase 12.2 — Unit tests for standalone Deepgram Listen (Flux v2) bridge.
Verifies URL generation, headers, audio streaming, runtime Configure messages,
and event handling.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from services.voice_agent.bridges.deepgram_standalone import DeepgramStandaloneBridge


@pytest.fixture
def bridge():
    return DeepgramStandaloneBridge(sample_rate=8000, model="flux-general-en")


class TestDeepgramStandaloneBridge:
    def test_url_construction(self, bridge):
        """
        URL must properly encode parameters for Flux v2 streaming with mu-law audio.
        """
        url = bridge.url
        assert "wss://api.deepgram.com/v2/listen?" in url
        assert "model=flux-general-en" in url
        assert "encoding=mulaw" in url
        assert "sample_rate=8000" in url
        assert "eot_threshold=0.6" in url

    @pytest.mark.asyncio
    async def test_connect_success(self, bridge):
        """
        Verify connect() passes authorization token and sets connection state.
        """
        mock_ws = AsyncMock()
        with patch("websockets.connect", AsyncMock(return_value=mock_ws)) as mock_connect:
            success = await bridge.connect()
            assert success is True
            assert bridge.is_connected is True
            assert bridge.ws == mock_ws
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_audio(self, bridge):
        """
        Verify raw audio bytes are forwarded to active websocket.
        """
        mock_ws = AsyncMock()
        bridge.ws = mock_ws
        bridge.is_connected = True

        audio_payload = b"\x00\x01\x02\x03" * 40
        await bridge.send_audio(audio_payload)
        mock_ws.send.assert_called_once_with(audio_payload)

    @pytest.mark.asyncio
    async def test_send_configure_message(self, bridge):
        """
        Verify dynamic EOT parameters are formatted cleanly in a Configure JSON message.
        """
        mock_ws = AsyncMock()
        bridge.ws = mock_ws
        bridge.is_connected = True

        await bridge.send_configure(eot_threshold=0.8, eot_timeout_ms=1200, eager_eot_threshold=0.6)
        mock_ws.send.assert_called_once()
        sent_payload = json.loads(mock_ws.send.call_args[0][0])
        assert sent_payload["type"] == "Configure"
        # Flux v2 schema — `processors` is Listen v1 and is rejected.
        assert sent_payload["thresholds"]["eot_threshold"] == 0.8
        assert sent_payload["thresholds"]["eot_timeout_ms"] == 1200
        assert sent_payload["thresholds"]["eager_eot_threshold"] == 0.6

    @pytest.mark.asyncio
    async def test_send_keep_alive(self, bridge):
        """
        Verify KeepAlive message format.
        """
        mock_ws = AsyncMock()
        bridge.ws = mock_ws
        bridge.is_connected = True

        await bridge.send_keep_alive()
        sent_payload = json.loads(mock_ws.send.call_args[0][0])
        assert sent_payload["type"] == "KeepAlive"

    @pytest.mark.asyncio
    async def test_receive_events(self, bridge):
        """
        Verify JSON events yielded from receive_events async generator.
        """
        async def fake_ws_messages():
            yield json.dumps({"type": "StartOfTurn"})
            yield json.dumps({"type": "EagerEndOfTurn"})
            yield json.dumps({"type": "EndOfTurn"})

        bridge.ws = fake_ws_messages()
        events = []
        async for evt in bridge.receive_events():
            events.append(evt["type"])

        assert events == ["StartOfTurn", "EagerEndOfTurn", "EndOfTurn"]
        assert bridge.is_connected is False
