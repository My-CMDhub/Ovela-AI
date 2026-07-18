"""
tests/test_cartesia_standalone.py
===================================
Phase 12.2 — Unit tests for standalone Cartesia Direct TTS bridge.
Verifies URL construction, transcript chunk sending, and barge-in cancellation.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from services.voice_agent.bridges.cartesia_standalone import CartesiaStandaloneBridge


@pytest.fixture
def bridge():
    return CartesiaStandaloneBridge(model_id="sonic-english", sample_rate=8000)


class TestCartesiaStandaloneBridge:
    def test_url_construction(self, bridge):
        """
        Verify Cartesia WebSocket URL includes version parameter.
        """
        url = bridge.url
        assert "wss://api.cartesia.ai/tts/websocket" in url
        assert "cartesia_version=2024-06-10" in url

    @pytest.mark.asyncio
    async def test_connect_success(self, bridge):
        """
        Verify connection establishment.
        """
        mock_ws = AsyncMock()
        with patch("websockets.connect", AsyncMock(return_value=mock_ws)) as mock_connect, \
             patch("core.config.settings.CARTESIA_API_KEY", "test_key_123"):
            success = await bridge.connect()
            assert success is True
            assert bridge.is_connected is True
            assert bridge.ws == mock_ws

    @pytest.mark.asyncio
    async def test_send_transcript_chunk(self, bridge):
        """
        Verify transcript chunks are wrapped in correct Cartesia JSON structure.
        """
        mock_ws = AsyncMock()
        bridge.ws = mock_ws
        bridge.is_connected = True

        await bridge.send_transcript_chunk(
            context_id="ctx_101",
            transcript="Hello from Coal Creek Motel",
            continue_stream=True,
        )
        mock_ws.send.assert_called_once()
        payload = json.loads(mock_ws.send.call_args[0][0])
        assert payload["context_id"] == "ctx_101"
        assert payload["model_id"] == "sonic-english"
        assert payload["transcript"] == "Hello from Coal Creek Motel"
        assert payload["output_format"]["encoding"] == "mulaw"
        assert payload["output_format"]["sample_rate"] == 8000
        assert payload["continue"] is True

    @pytest.mark.asyncio
    async def test_cancel_stream(self, bridge):
        """
        Verify instant barge-in cancellation payload.
        """
        mock_ws = AsyncMock()
        bridge.ws = mock_ws
        bridge.is_connected = True

        await bridge.cancel_stream("ctx_101")
        mock_ws.send.assert_called_once()
        payload = json.loads(mock_ws.send.call_args[0][0])
        assert payload["context_id"] == "ctx_101"
        assert payload["cancel"] is True
