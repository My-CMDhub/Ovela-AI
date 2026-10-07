"""
tests/test_tts_context_close.py
===============================
A turn must end its Cartesia context with `continue: false`, or Cartesia
emits `done` only on its own context timeout. Until then the turn's audio
reader waits, the agent stays AGENT_SPEAKING, and a caller's "yes" in that
window is treated as a backchannel and dropped.

The sender only marked a phrase as last if the end-of-stream sentinel was
already queued when it was sent. OpenAI streams with include_usage end one
network read after the last token, so the common case was: last phrase sent
with continue=True, sentinel arrives to an empty buffer, nothing closes the
context.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
from services.voice_agent.vad import ConversationState

# Stands in for Cartesia's context timeout, scaled down. The real one is
# seconds; the turn's reader is bounded at 15.
CARTESIA_CONTEXT_TIMEOUT_S = 1.5


async def _run_turn(tokens, stream_tail_s, barge_in_after_s=None):
    """
    Drive one real pipeline turn against a Cartesia that, like the real one,
    says `done` for a context only once it has been closed (or timed out).
    `stream_tail_s` is the gap between the last token and the end of the
    stream — the usage chunk's network read.
    """
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.cartesia = MagicMock()
    agent.cartesia.cancel_stream = AsyncMock()
    agent.is_running = True
    agent.state = ConversationState.AGENT_SPEAKING
    # A newer value on `self` must not be where the close goes.
    agent.current_context_id = "ctx_someone_else"

    sent = []
    closed = asyncio.Event()
    timed_out = []

    async def record(context_id, transcript, continue_stream=True):
        sent.append((context_id, transcript, continue_stream))
        if not continue_stream:
            closed.set()

    agent.cartesia.send_transcript_chunk = AsyncMock(side_effect=record)

    async def audio():
        yield {"type": "chunk", "context_id": "ctx_turn", "data": "QUJDRA=="}
        try:
            await asyncio.wait_for(closed.wait(), CARTESIA_CONTEXT_TIMEOUT_S)
        except asyncio.TimeoutError:
            timed_out.append(True)
        yield {"type": "done", "context_id": "ctx_turn"}

    agent.cartesia.receive_audio_events = audio

    async def llm(history):
        for token in tokens:
            yield token
        await asyncio.sleep(stream_tail_s)

    agent.llm_callback = llm
    agent._turn_id += 1

    # No pacing delay: it would give the sentinel time to land before the
    # last phrase is sent, which is the lucky case, not the one under test.
    with patch("services.voice_agent.cascaded_orchestrator.cognitive_delay", return_value=0):
        turn = asyncio.create_task(
            agent._run_parallel_streaming_pipeline(agent._turn_id, context_id="ctx_turn"))
        if barge_in_after_s is not None:
            await asyncio.sleep(barge_in_after_s)
            agent.state = ConversationState.AWAITING_INPUT     # trigger_barge_in
        await asyncio.wait_for(turn, timeout=20)

    return sent, bool(timed_out)


async def test_a_stream_that_ends_after_its_last_phrase_still_closes_the_context():
    # "Goodbye! " is released as soon as it arrives (whitespace follows the
    # "!"), and the stream only ends after the hang-up tool has run.
    sent, timed_out = await _run_turn(
        ["Thanks for calling, ", "goodbye! "], stream_tail_s=0.1)

    assert [s for s in sent if s[1]] == [
        ("ctx_turn", "Thanks for calling,", True),
        ("ctx_turn", "goodbye!", True),
    ]
    closes = [s for s in sent if s[1] == ""]
    assert closes == [("ctx_turn", "", False)], f"expected exactly one close, sent {sent}"
    assert sent[-1] == ("ctx_turn", "", False), "the close must come after the last phrase"
    assert not timed_out, "Cartesia only finished the turn on its own context timeout"


async def test_no_extra_close_when_the_last_phrase_already_closed_the_context():
    # The final "." is held for the next token, so the last phrase is sent
    # once the stream has ended — with continue=false on it.
    sent, timed_out = await _run_turn(
        ["Your room is booked. ", "See you Friday."], stream_tail_s=0.1)

    assert sent == [
        ("ctx_turn", "Your room is booked.", True),
        ("ctx_turn", "See you Friday.", False),
    ]
    assert not timed_out


async def test_no_extra_close_when_the_sentinel_was_already_queued():
    sent, _ = await _run_turn(["Breakfast is included. "], stream_tail_s=0)

    assert sent == [("ctx_turn", "Breakfast is included.", False)]


async def test_a_turn_that_lost_the_floor_sends_no_close():
    # barge-in cancels the context itself; a send from a turn that no longer
    # holds the floor is exactly what the turn guards exist to stop.
    sent, _ = await _run_turn(
        ["Let me read that back, ", "Jane. "], stream_tail_s=0.3, barge_in_after_s=0.1)

    assert sent, "the turn should have spoken before the barge-in"
    assert all(s[1] for s in sent), f"a barged-in turn sent a close: {sent}"
