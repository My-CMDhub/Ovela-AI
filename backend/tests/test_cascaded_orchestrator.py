"""
tests/test_cascaded_orchestrator.py
=====================================
Phase 12.3 — Unit tests for the CascadedPipelineOrchestrator.
Verifies bridge initialization, acoustic barge-in handling, Twilio mark tracking,
and Deepgram Flux v2 event orchestration.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
from services.voice_agent.vad import ConversationState


@pytest.fixture
def mock_twilio_ws():
    ws = AsyncMock()
    return ws


@pytest.fixture
def orchestrator(mock_twilio_ws):
    return CascadedPipelineOrchestrator(
        twilio_ws=mock_twilio_ws,
        stream_sid="MZ123456789",
    )


class TestCascadedPipelineOrchestrator:
    @pytest.mark.asyncio
    async def test_start_success(self, orchestrator):
        """
        Verify start connects both Deepgram and Cartesia standalone bridges.
        """
        with patch.object(orchestrator.deepgram, "connect", AsyncMock(return_value=True)) as mock_dg, \
             patch.object(orchestrator.cartesia, "connect", AsyncMock(return_value=True)) as mock_tts:
            success = await orchestrator.start()
            assert success is True
            assert orchestrator.is_running is True
            mock_dg.assert_called_once()
            mock_tts.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_failure_when_bridge_fails(self, orchestrator):
        """
        If Deepgram or Cartesia fails to connect, orchestrator must shut down safely.
        """
        with patch.object(orchestrator.deepgram, "connect", AsyncMock(return_value=False)), \
             patch.object(orchestrator.cartesia, "connect", AsyncMock(return_value=True)), \
             patch.object(orchestrator, "stop", AsyncMock()) as mock_stop:
            success = await orchestrator.start()
            assert success is False
            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_twilio_audio_forwards_to_deepgram(self, orchestrator):
        """
        All incoming audio packets from Twilio must be forwarded to Deepgram STT stream.
        """
        orchestrator.is_running = True
        with patch.object(orchestrator.deepgram, "send_audio", AsyncMock()) as mock_send:
            audio_bytes = b"\x00\x01\x02\x03" * 40  # 160 bytes
            await orchestrator.handle_twilio_audio(audio_bytes)
            mock_send.assert_called_once_with(audio_bytes)

    @pytest.mark.asyncio
    async def test_handle_twilio_audio_triggers_barge_in_on_speech(self, orchestrator):
        """
        When agent is speaking and local VAD detects speech (and immunity expired),
        trigger_barge_in must be invoked immediately.
        """
        orchestrator.is_running = True
        orchestrator.state = ConversationState.AGENT_SPEAKING
        with patch.object(orchestrator.deepgram, "send_audio", AsyncMock()), \
             patch.object(orchestrator.vad, "process_mulaw", return_value=True), \
             patch.object(orchestrator.vad, "is_immune", return_value=False), \
             patch.object(orchestrator, "trigger_barge_in", AsyncMock()) as mock_barge:
            audio_bytes = b"\x00\x01\x02\x03" * 40  # 160 bytes
            await orchestrator.handle_twilio_audio(audio_bytes)
            mock_barge.assert_called_once_with(reason="local_vad_acoustic")

    @pytest.mark.asyncio
    async def test_trigger_barge_in_sends_clear_and_cancels_cartesia(self, orchestrator):
        """
        Verify barge-in cuts Cartesia TTS stream, sends clear event to Twilio,
        and prunes conversation history per confirmed mark index.
        """
        orchestrator.state = ConversationState.AGENT_SPEAKING
        orchestrator.current_context_id = "ctx_test_999"
        orchestrator.history = [
            {"role": "user", "content": "I want a room"},
            {"role": "assistant", "content": "We have rooms available on Monday and Tuesday"},
        ]
        # Simulate Twilio confirming word index 3 ("We have rooms")
        mark_name = orchestrator.mark_tracker.register_word(3)
        orchestrator.mark_tracker.confirm_mark(mark_name)

        with patch.object(orchestrator.cartesia, "cancel_stream", AsyncMock()) as mock_cancel:
            await orchestrator.trigger_barge_in(reason="test")
            assert orchestrator.state == ConversationState.AWAITING_INPUT
            mock_cancel.assert_called_once_with("ctx_test_999")
            orchestrator.twilio_ws.send_text.assert_called_once()
            clear_payload = json.loads(orchestrator.twilio_ws.send_text.call_args[0][0])
            assert clear_payload["event"] == "clear"
            assert clear_payload["streamSid"] == "MZ123456789"
            assert orchestrator.history[-1]["content"] == "We have rooms"

    @pytest.mark.asyncio
    async def test_handle_user_turn_complete_with_cognitive_delay(self, orchestrator):
        """
        Verify turn completion routes transcript, applies cognitive delay for fast LLM,
        and streams resulting TTS to Twilio.
        """
        async def fake_llm(history):
            return "Sure I can check that for you right now."

        orchestrator.llm_callback = fake_llm
        orchestrator.state = ConversationState.AWAITING_INPUT

        # Mock Cartesia methods
        mock_send = AsyncMock()
        orchestrator.cartesia.send_transcript_chunk = mock_send
        async def fake_audio_events():
            yield {"type": "chunk", "data": "YXVkaW8="}
            yield {"type": "done"}
        orchestrator.cartesia.receive_audio_events = fake_audio_events

        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            await orchestrator.handle_user_turn_complete("Do you have availability?")
            assert len(orchestrator.history) == 2
            assert orchestrator.history[0]["content"] == "Do you have availability?"
            assert orchestrator.history[1]["content"] == "Sure I can check that for you right now."
            mock_sleep.assert_any_call(0.12)  # Fast tool call triggered 120ms cue
            assert orchestrator.state == ConversationState.AWAITING_INPUT
            mock_send.assert_called_once_with(
                context_id=orchestrator.current_context_id,
                transcript="Sure I can check that for you right now.",
                continue_stream=False
            )

    @pytest.mark.asyncio
    async def test_default_llm_callback(self, orchestrator):
        """
        Verify default LLM callback uses ADKOrchestrator query_stream or falls back.
        """
        history = [{"role": "user", "content": "Hello Ovela"}]
        with patch("services.adk.graph.ADKOrchestrator") as mock_adk_cls:
            mock_adk = MagicMock()
            async def fake_query_stream(user_id, session_id, text):
                yield "Hello! "
                yield "How can I help today?"
            mock_adk.query_stream = fake_query_stream
            mock_session = MagicMock()
            mock_session.id = "mock_sess"
            mock_adk.get_or_create_session = AsyncMock(return_value=mock_session)
            mock_adk_cls.return_value = mock_adk
            
            chunks = []
            async for chunk in orchestrator._default_llm_callback(history):
                chunks.append(chunk)
            assert chunks == ["Hello! ", "How can I help today?"]

    @pytest.mark.asyncio
    async def test_run_loop_processes_twilio_events(self, orchestrator):
        """
        Verify run_loop iterates through Twilio messages and dispatches start, media, mark, stop.
        """
        async def fake_iter_text():
            yield json.dumps({"event": "start", "start": {"streamSid": "STREAM_777"}})
            yield json.dumps({"event": "mark", "mark": {"name": "mark_word_2"}})
            yield json.dumps({"event": "stop"})

        orchestrator.twilio_ws.iter_text = fake_iter_text
        with patch.object(orchestrator.deepgram, "connect", AsyncMock(return_value=True)), \
             patch.object(orchestrator.cartesia, "connect", AsyncMock(return_value=True)), \
             patch.object(orchestrator, "process_deepgram_events", AsyncMock()), \
             patch.object(orchestrator, "handle_twilio_mark", AsyncMock()) as mock_mark, \
             patch.object(orchestrator, "stop", AsyncMock()) as mock_stop:
            await orchestrator.run_loop()
            assert orchestrator.stream_sid == "STREAM_777"
            mock_mark.assert_called_once_with("mark_word_2")
            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_split_buffer_into_phrases(self):
        """
        Verify that text buffer is correctly split on punctuation or length (>= 6 words).
        """
        from services.voice_agent.cascaded_orchestrator import split_buffer_into_phrases

        # Test punctuation split (without ending punctuation to leave remainder)
        phrases, rest = split_buffer_into_phrases("Hello, how are you today", is_final=False)
        assert phrases == ["Hello,"]
        assert rest == " how are you today"

        # Test word count split (>= 6 words)
        phrases, rest = split_buffer_into_phrases("one two three four five six seven", is_final=False)
        assert phrases == ["one two three four five six"]
        assert rest == " seven"

        # Test final flush
        phrases, rest = split_buffer_into_phrases("final words left", is_final=True)
        assert phrases == ["final words left"]
        assert rest == ""

    @pytest.mark.asyncio
    async def test_run_parallel_streaming_pipeline(self, orchestrator):
        """
        Verify parallel streaming pipeline collects tokens, sends them, and plays audio.
        """
        # Let's mock llm_callback to be an async generator yielding chunks
        async def fake_llm_stream(history):
            yield "Hello, "
            yield "this is a test "
            yield "of the parallel queue."

        orchestrator.llm_callback = fake_llm_stream
        orchestrator.state = ConversationState.AGENT_SPEAKING
        orchestrator.current_context_id = "ctx_parallel_test"

        # Mock Cartesia send_transcript_chunk
        mock_send = AsyncMock()
        orchestrator.cartesia.send_transcript_chunk = mock_send

        # Mock Cartesia receive_audio_events
        async def fake_audio_events():
            yield {"type": "chunk", "data": "YXVkaW8="} # "audio" in base64
            yield {"type": "done"}

        orchestrator.cartesia.receive_audio_events = fake_audio_events

        # Mock prepare_for_tts to return the text unchanged
        with patch("services.voice_agent.cascaded_orchestrator.prepare_for_tts", side_effect=lambda x: (x, [])) as mock_prep, \
             patch("asyncio.sleep", AsyncMock()):

            await orchestrator._run_parallel_streaming_pipeline()

            # The history should have the full aggregated content appended
            assert len(orchestrator.history) == 1
            assert orchestrator.history[0]["content"] == "Hello, this is a test of the parallel queue."

            # Verify send_transcript_chunk calls (without leading/trailing spaces because of stripping):
            assert mock_send.call_count == 2
            mock_send.assert_any_call(
                context_id="ctx_parallel_test",
                transcript="Hello,",
                continue_stream=True
            )
            mock_send.assert_any_call(
                context_id="ctx_parallel_test",
                transcript="this is a test of the parallel queue.",
                continue_stream=False
            )


