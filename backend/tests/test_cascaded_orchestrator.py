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
        orchestrator._agent_audio_started = True  # agent is audibly speaking
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
    async def test_no_barge_in_while_agent_is_thinking(self, orchestrator):
        """
        Regression: LLM think-time is 2-3s. Barge-in must stay disarmed until
        the first audio chunk actually reaches Twilio, or the caller saying
        "hello?" while waiting cancels the reply they are waiting for.
        """
        orchestrator.is_running = True
        orchestrator.state = ConversationState.AGENT_SPEAKING
        orchestrator._agent_audio_started = False   # thinking, not yet audible
        orchestrator.vad.process_mulaw = MagicMock(return_value=True)  # caller speaks
        orchestrator.vad.arm_immunity(duration_s=0.0)  # immunity expired
        orchestrator.trigger_barge_in = AsyncMock()

        await orchestrator.handle_twilio_audio(b"\xff" * 160)
        orchestrator.trigger_barge_in.assert_not_awaited()

        # Once audio is genuinely flowing, barge-in must work again.
        orchestrator._agent_audio_started = True
        await orchestrator.handle_twilio_audio(b"\xff" * 160)
        orchestrator.trigger_barge_in.assert_awaited_once()

    @staticmethod
    def _delta(content=None, tool_calls=None):
        """Build a minimal OpenAI streaming chunk."""
        ev = MagicMock()
        ev.choices = [MagicMock()]
        ev.choices[0].delta.content = content
        ev.choices[0].delta.tool_calls = tool_calls
        return ev

    @pytest.mark.asyncio
    async def test_default_llm_callback_streams_gpt_text(self, orchestrator):
        """
        The conversational driver is GPT (never ADK) and yields streamed text.
        """
        async def fake_stream(*_a, **_kw):
            for part in ("Hello! ", "How can I help today?"):
                yield TestCascadedPipelineOrchestrator._delta(content=part)

        orchestrator._context_ready = True
        orchestrator.tenant_config = {"voice_settings": {"llm_model": "gpt-4.1-nano"}}
        orchestrator.dispatcher = MagicMock()
        orchestrator._openai = MagicMock()
        orchestrator._openai.chat.completions.create = AsyncMock(
            return_value=fake_stream()
        )

        chunks = [c async for c in orchestrator._default_llm_callback(
            [{"role": "user", "content": "Hello Ovela"}]
        )]
        assert chunks == ["Hello! ", "How can I help today?"]

        # The DB-configured model must be the one actually requested.
        assert orchestrator._openai.chat.completions.create.call_args.kwargs["model"] == "gpt-4.1-nano"

    @pytest.mark.asyncio
    async def test_default_llm_callback_executes_tool_calls(self, orchestrator):
        """
        Streamed tool-call deltas are reassembled and dispatched, then the
        follow-up round streams the spoken answer.
        """
        tc = MagicMock()
        tc.index = 0
        tc.id = "call_1"
        tc.function.name = "check_availability"
        tc.function.arguments = '{"room_type": "any"}'

        async def round_one(*_a, **_kw):
            yield TestCascadedPipelineOrchestrator._delta(tool_calls=[tc])

        async def round_two(*_a, **_kw):
            yield TestCascadedPipelineOrchestrator._delta(content="We have a Queen available.")

        orchestrator._context_ready = True
        orchestrator.tenant_config = {"voice_settings": {"llm_model": "gpt-4.1-nano"}}
        orchestrator.dispatcher = MagicMock()
        orchestrator.dispatcher.execute = AsyncMock(return_value={"available": ["Queen"]})
        orchestrator._openai = MagicMock()
        orchestrator._openai.chat.completions.create = AsyncMock(
            side_effect=[round_one(), round_two()]
        )

        chunks = [c async for c in orchestrator._default_llm_callback(
            [{"role": "user", "content": "any rooms free?"}]
        )]

        orchestrator.dispatcher.execute.assert_awaited_once_with(
            "check_availability", {"room_type": "any"}
        )
        assert chunks == ["We have a Queen available."]

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

    @pytest.mark.asyncio
    async def test_stale_cartesia_context_does_not_kill_current_turn(self, orchestrator):
        """
        Regression: Cartesia multiplexes all contexts on one socket. After a
        barge-in cancel, the cancelled context still emits trailing chunks and a
        `done`. That stale `done` must NOT terminate the next turn's receiver —
        it previously did, and the caller heard silence on every turn following
        an interruption.
        """
        async def fake_llm_stream(history):
            yield "Here is your answer."

        orchestrator.llm_callback = fake_llm_stream
        orchestrator.state = ConversationState.AGENT_SPEAKING
        orchestrator.current_context_id = "ctx_current"
        orchestrator.stream_sid = "MZtest"
        orchestrator.cartesia.send_transcript_chunk = AsyncMock()

        sent_media = []
        async def capture(payload):
            if '"media"' in payload:
                sent_media.append(payload)
        orchestrator.twilio_ws.send_text = AsyncMock(side_effect=capture)

        async def fake_audio_events():
            # Leftovers from the cancelled previous turn arrive first.
            yield {"type": "chunk", "context_id": "ctx_cancelled", "data": "c3RhbGU="}
            yield {"type": "done",  "context_id": "ctx_cancelled"}
            # This turn's real audio follows and must still be delivered.
            yield {"type": "chunk", "context_id": "ctx_current", "data": "YXVkaW8="}
            yield {"type": "done",  "context_id": "ctx_current"}

        orchestrator.cartesia.receive_audio_events = fake_audio_events

        with patch("services.voice_agent.cascaded_orchestrator.prepare_for_tts", side_effect=lambda x: (x, [])), \
             patch("asyncio.sleep", AsyncMock()):
            await orchestrator._run_parallel_streaming_pipeline()

        # The current turn's audio reached Twilio despite the stale `done`.
        assert any("YXVkaW8=" in p for p in sent_media), "current turn audio was dropped"
        assert not any("c3RhbGU=" in p for p in sent_media), "stale audio was forwarded"

    # ------------------------------------------------------------------
    # Control-flow tool actions (hang_up_call)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_hangup_action_from_dispatcher_is_recorded(self, orchestrator):
        """
        Regression: the dispatcher returns {"action": "hangup"} for hang_up_call,
        but the cascaded tool loop only forwarded the dict back to the LLM and
        never read `action`. The model then narrated a goodbye while the call
        stayed open — verified live, hang_up_call fired 3x on a 566s call.
        """
        tc = MagicMock()
        tc.index = 0
        tc.id = "call_hangup"
        tc.function.name = "hang_up_call"
        tc.function.arguments = '{"farewell_message": "Thanks for calling, goodbye."}'

        async def round_one(*_a, **_kw):
            yield TestCascadedPipelineOrchestrator._delta(tool_calls=[tc])

        async def round_two(*_a, **_kw):
            yield TestCascadedPipelineOrchestrator._delta(content="Thanks for calling, goodbye.")

        orchestrator._context_ready = True
        orchestrator.tenant_config = {"voice_settings": {"llm_model": "gpt-4.1-nano"}}
        orchestrator.dispatcher = MagicMock()
        orchestrator.dispatcher.execute = AsyncMock(return_value={
            "action": "hangup", "message": "Thanks for calling, goodbye."
        })
        orchestrator._openai = MagicMock()
        orchestrator._openai.chat.completions.create = AsyncMock(
            side_effect=[round_one(), round_two()]
        )

        [c async for c in orchestrator._default_llm_callback(
            [{"role": "user", "content": "that's all, bye"}]
        )]

        assert orchestrator._pending_hangup is True, "hangup action was dropped by the tool loop"

    @pytest.mark.asyncio
    async def test_pending_hangup_terminates_call_after_farewell(self, orchestrator):
        """
        A recorded hangup must fire only once the farewell has finished
        streaming — never mid-phrase.
        """
        async def fake_llm_stream(history):
            orchestrator._pending_hangup = True
            yield "Thanks for calling, goodbye."

        orchestrator.llm_callback = fake_llm_stream
        orchestrator.state = ConversationState.AGENT_SPEAKING
        orchestrator.current_context_id = "ctx_bye"
        orchestrator.cartesia.send_transcript_chunk = AsyncMock()

        async def fake_audio_events():
            yield {"type": "chunk", "data": "YXVkaW8="}
            yield {"type": "done"}

        orchestrator.cartesia.receive_audio_events = fake_audio_events

        with patch("services.voice_agent.cascaded_orchestrator.prepare_for_tts", side_effect=lambda x: (x, [])), \
             patch("asyncio.sleep", AsyncMock()), \
             patch.object(orchestrator, "_hangup_call", AsyncMock()) as mock_hangup:
            await orchestrator._run_parallel_streaming_pipeline()

        mock_hangup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pending_hangup_aborted_when_user_interrupts_farewell(self, orchestrator):
        """
        If the caller speaks during the farewell they are not done talking.
        Hanging up on them is worse than the bug this fixes.
        """
        async def fake_llm_stream(history):
            orchestrator._pending_hangup = True
            yield "Thanks for calling, goodbye."
            # trigger_barge_in() drops the state back to AWAITING_INPUT.
            orchestrator.state = ConversationState.AWAITING_INPUT

        orchestrator.llm_callback = fake_llm_stream
        orchestrator.state = ConversationState.AGENT_SPEAKING
        orchestrator.current_context_id = "ctx_bye"
        orchestrator.cartesia.send_transcript_chunk = AsyncMock()

        async def fake_audio_events():
            yield {"type": "chunk", "data": "YXVkaW8="}
            yield {"type": "done"}

        orchestrator.cartesia.receive_audio_events = fake_audio_events

        with patch("services.voice_agent.cascaded_orchestrator.prepare_for_tts", side_effect=lambda x: (x, [])), \
             patch("asyncio.sleep", AsyncMock()), \
             patch.object(orchestrator, "_hangup_call", AsyncMock()) as mock_hangup:
            await orchestrator._run_parallel_streaming_pipeline()

        mock_hangup.assert_not_awaited()
        assert orchestrator._pending_hangup is False

    @pytest.mark.asyncio
    async def test_hangup_call_posts_completed_status_to_twilio(self, orchestrator):
        """
        The actual termination is a Twilio REST status update — the only thing
        that ends a live PSTN call.
        """
        orchestrator.call_sid = "CA_test_sid"
        orchestrator.is_running = True

        mock_response = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("services.voice_agent.cascaded_orchestrator.httpx.AsyncClient", return_value=mock_ctx):
            await orchestrator._hangup_call()

        assert mock_client.post.await_count == 1
        assert mock_client.post.await_args.kwargs["data"] == {"Status": "completed"}
        assert "CA_test_sid" in mock_client.post.await_args.args[0]
        assert orchestrator.is_running is False

    @pytest.mark.asyncio
    async def test_transfer_action_from_dispatcher_is_recorded(self, orchestrator):
        """
        Regression: same dropped-`action` root cause as hang_up_call. The agent
        told the caller "I'll transfer you to reception now" and then kept
        talking — the transfer never happened.
        """
        tc = MagicMock()
        tc.index = 0
        tc.id = "call_transfer"
        tc.function.name = "transfer_to_staff"
        tc.function.arguments = '{}'

        async def round_one(*_a, **_kw):
            yield TestCascadedPipelineOrchestrator._delta(tool_calls=[tc])

        async def round_two(*_a, **_kw):
            yield TestCascadedPipelineOrchestrator._delta(content="Sure, transferring you now.")

        orchestrator._context_ready = True
        orchestrator.tenant_config = {"voice_settings": {"llm_model": "gpt-4.1-nano"}}
        orchestrator.dispatcher = MagicMock()
        orchestrator.dispatcher.execute = AsyncMock(return_value={
            "action": "transfer",
            "transfer_to": "+61399990000",
            "message": "Sure, I'll transfer you to reception now.",
        })
        orchestrator._openai = MagicMock()
        orchestrator._openai.chat.completions.create = AsyncMock(
            side_effect=[round_one(), round_two()]
        )

        [c async for c in orchestrator._default_llm_callback(
            [{"role": "user", "content": "can I speak to a human"}]
        )]

        assert orchestrator._pending_transfer == "+61399990000", \
            "transfer action was dropped by the tool loop"

    @pytest.mark.asyncio
    async def test_pending_transfer_updates_call_with_dial_twiml(self, orchestrator):
        """
        A transfer is a TwiML update on the live call — <Dial> to staff, with a
        fallback back to the AI if nobody answers.
        """
        orchestrator.call_sid = "CA_test_sid"
        orchestrator.is_running = True

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=MagicMock())
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("services.voice_agent.cascaded_orchestrator.httpx.AsyncClient", return_value=mock_ctx):
            await orchestrator._transfer_call("+61399990000")

        twiml = mock_client.post.await_args.kwargs["data"]["Twiml"]
        assert "<Dial" in twiml
        assert "+61399990000" in twiml
        assert "CA_test_sid" in mock_client.post.await_args.args[0]
        assert orchestrator.is_running is False

    @pytest.mark.asyncio
    async def test_pending_transfer_fires_after_the_spoken_handoff(self, orchestrator):
        """
        The transfer must land after "I'll transfer you now" has been streamed,
        otherwise the caller is moved in silence.
        """
        async def fake_llm_stream(history):
            orchestrator._pending_transfer = "+61399990000"
            yield "Sure, transferring you now."

        orchestrator.llm_callback = fake_llm_stream
        orchestrator.state = ConversationState.AGENT_SPEAKING
        orchestrator.current_context_id = "ctx_transfer"
        orchestrator.cartesia.send_transcript_chunk = AsyncMock()

        async def fake_audio_events():
            yield {"type": "chunk", "data": "YXVkaW8="}
            yield {"type": "done"}

        orchestrator.cartesia.receive_audio_events = fake_audio_events

        with patch("services.voice_agent.cascaded_orchestrator.prepare_for_tts", side_effect=lambda x: (x, [])), \
             patch("asyncio.sleep", AsyncMock()), \
             patch.object(orchestrator, "_transfer_call", AsyncMock()) as mock_transfer:
            await orchestrator._run_parallel_streaming_pipeline()

        mock_transfer.assert_awaited_once_with("+61399990000")

    @pytest.mark.asyncio
    async def test_transfer_without_call_sid_does_not_crash(self, orchestrator):
        """
        No Call SID means no transfer is possible; the call must survive it.
        """
        orchestrator.call_sid = ""
        orchestrator.is_running = True

        await orchestrator._transfer_call("+61399990000")

        assert orchestrator.is_running is True

    @pytest.mark.asyncio
    async def test_hangup_call_is_idempotent(self, orchestrator):
        """
        The model called hang_up_call three times on one call. A second
        termination must not fire a second Twilio request.
        """
        orchestrator.call_sid = "CA_test_sid"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=MagicMock())
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("services.voice_agent.cascaded_orchestrator.httpx.AsyncClient", return_value=mock_ctx):
            await orchestrator._hangup_call()
            await orchestrator._hangup_call()

        assert mock_client.post.await_count == 1


