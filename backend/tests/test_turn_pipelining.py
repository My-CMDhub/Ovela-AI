"""
tests/test_turn_pipelining.py
=============================
Three faults heard on call 2 (16 September, v425), in the owner's words:

  "I ask a new question, the system replies to my LAST question, then I must
   wait several seconds. After that pause it detects the new question and
   finally answers it. The latency is inconsistent and feels unnatural."

The log fingerprint is unmissable once you look for it:

    05:48:28.412472  EagerEndOfTurn
    05:48:28.412677  TurnResumed
    05:48:28.412808  EagerEndOfTurn
    05:48:28.412928  User finished turn: 'do you allow pets?'

Four Deepgram events handled inside 0.5ms. Real speech does not produce
events 0.5ms apart — that is a backlog draining. `process_deepgram_events`
awaits the whole turn (LLM + TTS + every audio byte + the playback drain)
inside its own `async for`, so nothing the caller says is even READ until
the previous answer has finished playing.

Sentry cannot see this delay: Span 1 opens inside
`handle_user_turn_complete`, which is after the queued read. Every latency
figure we have excludes it.

The tests measure the three consequences separately. Each is written to fail
against the current code — that is the point of them.
"""

import asyncio
import time

import pytest

from unittest.mock import AsyncMock, MagicMock

from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
from services.voice_agent.interruption import MarkTracker
from services.voice_agent.vad import ConversationState

# One "turn" of agent speech, scaled down. Real replies on the call ran 5-9s;
# the defect is proportional to reply length, so any value above the test's
# tolerance demonstrates it.
REPLY_PLAYOUT_S = 0.40

# What a caller should tolerate between finishing a question and the system
# having at least READ it. Not answered — read.
READ_BUDGET_S = 0.05


class FakeDeepgram:
    """
    A socket, not a generator.

    Events are produced on a schedule by a task that does not care whether
    anyone is reading, which is what a real WebSocket does. A plain async
    generator would only produce its next event when the consumer asked for
    it, and would therefore hide the exact bug being measured.
    """

    def __init__(self, script):
        self.script = script                  # [(delay_s, event_dict), ...]
        self.queue: asyncio.Queue = asyncio.Queue()
        self.available_at: dict = {}          # transcript -> when it hit the queue

    async def produce(self):
        for delay, event in self.script:
            await asyncio.sleep(delay)
            key = event.get("transcript") or event.get("event")
            self.available_at.setdefault(key, time.monotonic())
            await self.queue.put(event)

    async def receive_events(self):
        while True:
            event = await self.queue.get()
            if event is None:
                return
            yield event


def _agent(pipeline):
    """An orchestrator with the turn pipeline replaced by a known-length one."""
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.cartesia = MagicMock()
    agent.cartesia.cancel_stream = AsyncMock()
    agent.is_running = True
    agent.state = ConversationState.AWAITING_INPUT
    agent._run_parallel_streaming_pipeline = pipeline
    return agent


async def test_a_new_question_is_read_while_the_last_answer_is_still_playing():
    """
    The caller's words must reach `handle_user_turn_complete` when Deepgram
    sends them, not when the previous answer finishes playing. End to end now:
    the read loop enqueues, `_turn_worker` reads ahead and takes the floor.

    Fails today by roughly one reply's length, every time, and the size of
    the delay depends on how long the last answer was — which is why it feels
    inconsistent rather than merely slow.
    """
    handled_at: dict = {}

    async def pipeline(*_a, **_kw):
        # Stands in for LLM + TTS + audio send + playback drain.
        agent.state = ConversationState.AGENT_SPEAKING
        await asyncio.sleep(REPLY_PLAYOUT_S)
        agent.state = ConversationState.AWAITING_INPUT

    agent = _agent(pipeline)
    original = agent.handle_user_turn_complete

    async def timed(transcript):
        handled_at[transcript] = time.monotonic()
        await original(transcript)

    agent.handle_user_turn_complete = timed

    dg = FakeDeepgram([
        (0.00, {"type": "TurnInfo", "event": "EndOfTurn", "transcript": "what rooms do you have?"}),
        # The caller cuts in a tenth of a second later with the real question.
        (0.10, {"type": "TurnInfo", "event": "EndOfTurn", "transcript": "and what about the price?"}),
    ])
    agent.deepgram = dg

    producer = asyncio.create_task(dg.produce())
    reader = asyncio.create_task(agent.process_deepgram_events())
    worker = asyncio.create_task(agent._turn_worker())
    await producer
    await asyncio.sleep(REPLY_PLAYOUT_S * 3)
    reader.cancel()
    worker.cancel()

    second = "and what about the price?"
    waited = handled_at[second] - dg.available_at[second]
    assert waited < READ_BUDGET_S, (
        f"the second question sat unread for {waited * 1000:.0f}ms while the first "
        f"answer played ({REPLY_PLAYOUT_S * 1000:.0f}ms of audio). Deepgram had "
        f"delivered it; the read loop was blocked awaiting the turn."
    )


async def test_turn_resumed_does_not_cancel_the_reply_being_spoken():
    """
    `_pending_llm_task` meant two things: the eager pre-warm task TurnResumed
    is supposed to cancel, and the live turn's streaming pipeline. Same
    attribute, so a TurnResumed can cancel the answer the caller is listening
    to — and the reply is appended to history only after its playback drain,
    so the agent keeps no record of an answer the caller heard and gives it
    again.

    **This is a guard, not a regression test, and the difference matters.**
    A review established that the cancel was unreachable before the turn
    stopped being awaited in the read loop: this loop is the only reader of
    Deepgram events, it was blocked inside the turn, so a TurnResumed was not
    read until the turn was done and `.done()` made the cancel a no-op.
    Reverting the TurnResumed change alone turns this test red; reverting it
    together with the non-blocking change — the real parent commit — and it
    passes. So the hazard is one the non-blocking change created, and the
    earlier claim that it explains the caller repeating "about my previous
    question?" on call 2 was wrong. That was the event backlog.
    """
    async def pipeline(*_a, **_kw):
        agent.state = ConversationState.AGENT_SPEAKING
        await asyncio.sleep(REPLY_PLAYOUT_S)
        # Where the real pipeline appends: after the drain, so a cancel
        # anywhere above this line loses the turn.
        agent.history.append({"role": "assistant", "content": "We have queen, twin and family rooms."})
        agent.state = ConversationState.AWAITING_INPUT

    agent = _agent(pipeline)
    dg = FakeDeepgram([
        (0.00, {"type": "TurnInfo", "event": "EndOfTurn", "transcript": "what rooms do you have?"}),
        (0.05, {"type": "TurnInfo", "event": "TurnResumed"}),
    ])
    agent.deepgram = dg

    producer = asyncio.create_task(dg.produce())
    reader = asyncio.create_task(agent.process_deepgram_events())
    worker = asyncio.create_task(agent._turn_worker())
    await producer
    await asyncio.sleep(REPLY_PLAYOUT_S * 3)
    reader.cancel()
    worker.cancel()

    spoken = [m for m in agent.history if m["role"] == "assistant"]
    assert spoken, (
        "the reply the caller heard is missing from history — a TurnResumed "
        "cancelled the live turn's pipeline task, so the agent will answer "
        "the same question again"
    )


def test_a_stale_mark_from_the_previous_turn_cannot_move_this_turn_index():
    """
    Mark names are `mark_word_<n>` with no turn in them, and Twilio keeps
    echoing marks for audio it had already queued when the barge-in landed.
    A late echo of turn 1's `mark_word_18` lands while turn 2 is speaking and,
    because turn 2 has registered that same name, moves turn 2's confirmed
    index from 3 words to 18.

    `confirmed_index` is what barge-in prunes history against, so an index
    that is too high makes the agent believe the caller heard sentences that
    were never played, and it will not repeat them.
    """
    tracker = MarkTracker()

    # Turn 1: a long answer, cut off. The names are whatever the tracker
    # hands to Twilio — the test must not know the scheme, only that a name
    # from one turn cannot speak for another.
    turn_one = {i: tracker.register_word(i) for i in range(1, 21)}
    tracker.confirm_mark(turn_one[18])
    assert tracker.confirmed_index == 18
    tracker.reset()

    # Turn 2: the caller has heard three words so far.
    turn_two = {i: tracker.register_word(i) for i in range(1, 21)}
    tracker.confirm_mark(turn_two[3])
    assert tracker.confirmed_index == 3

    # Turn 1's echo finally arrives.
    tracker.confirm_mark(turn_one[18])

    assert tracker.confirmed_index == 3, (
        f"a stale mark from the previous turn moved the index to "
        f"{tracker.confirmed_index}; the caller has heard 3 words"
    )


class FakeCartesia:
    """
    Cartesia's shape: one socket multiplexing contexts, emitting chunks faster
    than real time, with a gap so a turn can be overtaken mid-stream.
    """

    def __init__(self, chunks=8, gap_s=0.03, context_id=None):
        self.chunks = chunks
        self.gap_s = gap_s
        self.context_id = context_id
        self.cancel_stream = AsyncMock()
        self.send_transcript_chunk = AsyncMock()
        self.connect = AsyncMock(return_value=True)
        self.close = AsyncMock()

    async def receive_audio_events(self):
        for _ in range(self.chunks):
            await asyncio.sleep(self.gap_s)
            yield {"type": "chunk", "context_id": self.context_id, "data": "QUJDRA=="}
        yield {"type": "done", "context_id": self.context_id}


async def test_the_old_turns_audio_stops_when_a_new_turn_takes_the_floor():
    """
    "If I keep interrupting, the new answer overlaps the previous one."

    Drives the real pipeline, then takes the floor away mid-stream the way a
    new turn does: barge-in sets AWAITING_INPUT, and `handle_user_turn_complete`
    sets AGENT_SPEAKING straight back three lines later for the new turn.

    The audio sender's only stop condition used to be that shared
    `self.state`, so the previous turn's receiver — still alive, blocked on
    Cartesia — woke up, re-read the flag, found AGENT_SPEAKING, and carried on
    writing the OLD reply into the same Twilio socket the new reply was using.
    The caller heard both.

    The context_id filter does not catch it: a stale receiver compares events
    against the context it captured itself, so its own trailing chunks match
    and pass. A receiver has to stop when ITS turn ends, not when the agent
    happens not to be speaking.
    """
    media_after_handover = []
    handed_over = asyncio.Event()

    ws = AsyncMock()

    async def record(payload):
        import json as _json
        if handed_over.is_set() and _json.loads(payload).get("event") == "media":
            media_after_handover.append(payload)

    ws.send_text = AsyncMock(side_effect=record)

    agent = CascadedPipelineOrchestrator(twilio_ws=ws, stream_sid="MZtest")
    agent.cartesia = FakeCartesia(chunks=10, gap_s=0.03)
    agent.is_running = True
    agent.state = ConversationState.AGENT_SPEAKING
    agent.current_context_id = "ctx_old"
    agent.cartesia.context_id = "ctx_old"

    async def llm():
        for token in ("We have queen, ", "twin, ", "family ", "and spa rooms."):
            yield token

    agent.llm_callback = lambda history: llm()

    agent._turn_id += 1
    turn = asyncio.create_task(agent._run_parallel_streaming_pipeline(
        agent._turn_id, context_id="ctx_old"))

    # Let the reply get under way, then hand the floor to a new turn.
    await asyncio.sleep(0.12)
    agent.state = ConversationState.AWAITING_INPUT       # trigger_barge_in
    agent._turn_id += 1                                  # a new turn begins
    handed_over.set()
    agent.state = ConversationState.AGENT_SPEAKING       # handle_user_turn_complete

    await asyncio.sleep(0.25)
    turn.cancel()

    assert not media_after_handover, (
        f"{len(media_after_handover)} media frames of the previous turn were still "
        f"written to Twilio after the new turn took the floor — that is the overlap "
        f"the caller hears"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Four faults a review found in the commit above. Making turns concurrent was
# right; leaving the things a turn owns on `self` was not. An overtaken turn
# winds down while its successor speaks, so anything read off `self` at use
# time belongs to whichever turn wrote it last.
# ─────────────────────────────────────────────────────────────────────────────


async def test_two_turns_never_put_two_readers_on_the_cartesia_socket():
    """
    The call-killer. Cartesia multiplexes every context over ONE websocket,
    and each turn was starting its own reader. `websockets` refuses the
    second: "cannot call recv while another coroutine is already running
    recv". That ConcurrencyError lands in `receive_audio_events`' bare
    `except Exception`, which sets `is_connected = False` — and from then on
    `send_transcript_chunk` returns at its first line, silently. One
    interruption and the caller hears dead air until they hang up.

    Run against a real `websockets` server and the real bridge, because a
    mock at a provider boundary tests our assumption instead of their
    contract — and the contract here IS the failure.
    """
    import json as _json

    import websockets

    from services.voice_agent.bridges.cartesia_standalone import (
        CartesiaStandaloneBridge,
    )

    received = []

    async def cartesia(ws):
        # Answers each transcript with one chunk and then goes quiet, which is
        # what leaves a reader parked in recv() with nothing to wake it — the
        # state a cancelled context leaves behind.
        async for raw in ws:
            msg = _json.loads(raw)
            received.append(msg)
            if msg.get("transcript"):
                await ws.send(_json.dumps({
                    "type": "chunk", "context_id": msg["context_id"], "data": "QUJDRA==",
                }))

    server = await websockets.serve(cartesia, "127.0.0.1", 8797)
    bridge = CartesiaStandaloneBridge()
    bridge.ws = await websockets.connect("ws://127.0.0.1:8797")
    bridge.is_connected = True

    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.cartesia = bridge
    agent.is_running = True

    async def llm(text):
        for token in text.split(" "):
            yield token + " "

    try:
        # Turn 1 starts speaking.
        agent.state = ConversationState.AGENT_SPEAKING
        agent.current_context_id = "ctx_one"
        agent._turn_id += 1
        first = asyncio.create_task(agent._run_parallel_streaming_pipeline(
            agent._turn_id, context_id="ctx_one"))
        agent.llm_callback = lambda h: llm("We have queen and twin rooms.")
        await asyncio.sleep(0.2)

        # The caller interrupts and turn 2 takes the floor.
        agent.state = ConversationState.AWAITING_INPUT
        agent.current_context_id = "ctx_two"
        agent.state = ConversationState.AGENT_SPEAKING
        agent.llm_callback = lambda h: llm("Breakfast is included.")
        agent._turn_id += 1
        second = asyncio.create_task(agent._run_parallel_streaming_pipeline(
            agent._turn_id, context_id="ctx_two"))
        await asyncio.sleep(0.4)

        assert bridge.is_connected, (
            "the second turn's reader killed the Cartesia socket — every phrase "
            "of every later turn is now dropped before it reaches the provider, "
            "silently, for the rest of the call"
        )
        spoken_second = [m for m in received if m.get("context_id") == "ctx_two"]
        assert spoken_second, "turn 2 reached the caller's ear not at all"
    finally:
        for t in (first, second):
            t.cancel()
        await bridge.ws.close()
        server.close()
        await server.wait_closed()


async def test_the_old_turn_does_not_synthesise_into_the_new_turns_context():
    """
    `context_id=self.current_context_id` was read at SEND time — and the
    cognitive-pacing delay sits between the turn check and that send with no
    re-check. So the floor can change mid-sleep and the tail of the previous
    answer is synthesised inside the NEW turn's context. The caller hears the
    old reply stutter into the new one, and the context_id filter cannot
    reject it because the id it carries is genuinely current.

    The handover is timed to land inside that delay, because that is the only
    window where it happens — a test that flips the floor anywhere else is
    stopped by the turn guard and proves nothing.
    """
    from unittest.mock import patch

    sent = []

    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.cartesia = MagicMock()
    agent.cartesia.cancel_stream = AsyncMock()

    async def record(context_id, transcript, continue_stream=True):
        sent.append((context_id, transcript))

    agent.cartesia.send_transcript_chunk = AsyncMock(side_effect=record)

    async def audio():
        while True:
            await asyncio.sleep(0.05)
            yield {"type": "chunk", "context_id": "ctx_one", "data": "QUJDRA=="}

    agent.cartesia.receive_audio_events = audio
    agent.is_running = True
    agent.state = ConversationState.AGENT_SPEAKING

    async def llm(history):
        yield "Check-in is from two p.m."

    agent.llm_callback = llm
    agent.current_context_id = "ctx_one"
    agent._turn_id += 1

    # A long, deterministic pacing delay: the real one is 0-300ms depending on
    # how fast the model answered, and the race needs the window open.
    with patch("services.voice_agent.cascaded_orchestrator.cognitive_delay",
               return_value=300):
        turn = asyncio.create_task(agent._run_parallel_streaming_pipeline(
            agent._turn_id, context_id="ctx_one"))
        await asyncio.sleep(0.1)          # inside the pacing delay now

        # Barge-in, then turn 2 arms itself with a new context — mid-sleep.
        agent.state = ConversationState.AWAITING_INPUT
        agent.current_context_id = "ctx_two"
        agent._turn_id += 1
        agent.state = ConversationState.AGENT_SPEAKING
        await asyncio.sleep(0.4)
        turn.cancel()

    leaked = [t for ctx, t in sent if ctx == "ctx_two"]
    assert not leaked, (
        f"the previous turn synthesised {leaked!r} into the new turn's context — "
        f"the caller hears the old answer inside the new one"
    )


async def test_an_overtaken_turn_does_not_finish_the_new_turns_transaction():
    """
    The teardown read `self._sentry_transaction` and `self._span_1` by name,
    so an overtaken turn finished the transaction its successor had just
    opened. Span 1 for that turn then reads ~0ms, `first_audio_latency_ms` is
    set on a closed transaction, and the overtaken turn's own transaction
    leaks unfinished.

    Which makes this the finding that quietly poisons the evidence for every
    other fix: after the first interruption, the latency numbers are fiction.
    """
    class Span:
        def __init__(self):
            self.finishes = 0
            self.timestamp = None

        def start_child(self, **kw):
            return Span()

        def set_data(self, *a):
            pass

        def finish(self):
            self.finishes += 1
            self.timestamp = "done"

    old_txn, old_span1 = Span(), Span()
    new_txn, new_span1 = Span(), Span()

    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.cartesia = MagicMock()
    agent.cartesia.cancel_stream = AsyncMock()
    agent.cartesia.send_transcript_chunk = AsyncMock()

    async def audio():
        while True:
            await asyncio.sleep(0.05)
            yield {"type": "chunk", "context_id": "ctx_one", "data": "QUJDRA=="}

    agent.cartesia.receive_audio_events = audio
    agent.is_running = True
    agent.state = ConversationState.AGENT_SPEAKING

    # The old turn must still be mid-reply when the new turn installs its
    # transaction, and must reach its teardown afterwards — otherwise the
    # teardown runs before there is anything of the new turn's to damage and
    # the test passes whatever the code does.
    overtaken = asyncio.Event()

    async def llm(history):
        yield "Check-in is from two p.m."
        await overtaken.wait()
        yield " And checkout is ten."

    agent.llm_callback = llm
    agent._turn_id += 1
    turn = asyncio.create_task(agent._run_parallel_streaming_pipeline(
        agent._turn_id, context_id="ctx_one",
        transaction=old_txn, span_1=old_span1))
    await asyncio.sleep(0.15)

    # Turn 2 takes the floor and installs its own transaction.
    agent.state = ConversationState.AWAITING_INPUT
    agent._turn_id += 1
    agent._sentry_transaction = new_txn
    agent._span_1 = new_span1
    agent.state = ConversationState.AGENT_SPEAKING
    overtaken.set()                     # the old turn now runs its teardown
    await asyncio.sleep(0.3)
    turn.cancel()

    assert new_txn.finishes == 0, "the overtaken turn finished the new turn's transaction"
    assert new_span1.finishes == 0, "the overtaken turn finished the new turn's Span 1"


async def test_a_promise_from_an_earlier_turn_is_not_kept_by_a_later_one():
    """
    `_pending_hangup` / `_pending_transfer` were consumed by whichever
    teardown ran first. Demonstrated by the review: a transfer promised in
    turn 1 was dialled by turn 2's teardown, after turn 2 had answered a
    different question. The mirror case is worse — a hangup promised in turn 1
    drops the line at the end of turn 2's answer, so the caller asks a
    follow-up, gets it answered, and the call ends.
    """
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.cartesia = MagicMock()
    agent.cartesia.cancel_stream = AsyncMock()
    agent.cartesia.send_transcript_chunk = AsyncMock()
    agent._transfer_call = AsyncMock()
    agent._hangup_call = AsyncMock()

    async def audio():
        yield {"type": "chunk", "context_id": "ctx_two", "data": "QUJDRA=="}
        yield {"type": "done", "context_id": "ctx_two"}

    agent.cartesia.receive_audio_events = audio
    agent.is_running = True
    agent.state = ConversationState.AGENT_SPEAKING

    async def llm(history):
        yield "Breakfast is included."

    agent.llm_callback = llm

    # Turn 1 promised a transfer and was then interrupted.
    agent._turn_id = 1
    agent._pending_transfer = "+61300000000"
    agent._pending_turn = 1

    # Turn 2 answers something else and runs its teardown.
    agent._turn_id = 2
    await agent._run_parallel_streaming_pipeline(2, context_id="ctx_two")

    agent._transfer_call.assert_not_called()
    assert agent._pending_transfer is None, "the abandoned promise is still armed"


# ─────────────────────────────────────────────────────────────────────────────
# A second review found that making turns concurrent was the mistake: all the
# per-turn state lives on the orchestrator, which is correct for exactly one
# live turn. The read loop now enqueues and `_turn_worker` answers one turn at
# a time, so the invariant the class was written for is back.
# ─────────────────────────────────────────────────────────────────────────────


async def test_only_one_turn_is_ever_live():
    """
    Two turns sharing one orchestrator cost a silenced Cartesia socket, a
    transfer dialled by the wrong turn, and an answer the caller heard
    vanishing from history. The worker must take the floor from a turn before
    the next one starts, and wait for it to let go.

    **Two independent things enforce this, so reverting either one leaves it
    green** — worth knowing before trusting it. `await self._turn_task` means
    cancelling the handler cancels the pipeline with it (awaiting a Task
    targets that Task's cancellation), and `_abandon_current_turn` cancels and
    joins it explicitly. Removing both — which is the fire-and-forget model of
    948a54d — turns this red at peak == 2. Defence in depth by accident rather
    than design, but the redundancy is worth keeping.
    """
    live = 0
    peak = 0

    async def pipeline(*_a, **_kw):
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        agent.state = ConversationState.AGENT_SPEAKING
        try:
            await asyncio.sleep(REPLY_PLAYOUT_S)
            agent.state = ConversationState.AWAITING_INPUT
        finally:
            live -= 1

    agent = _agent(pipeline)
    dg = FakeDeepgram([
        (0.00, {"type": "TurnInfo", "event": "EndOfTurn", "transcript": "what rooms do you have?"}),
        (0.05, {"type": "TurnInfo", "event": "EndOfTurn", "transcript": "and the price?"}),
        (0.05, {"type": "TurnInfo", "event": "EndOfTurn", "transcript": "what about breakfast?"}),
    ])
    agent.deepgram = dg

    producer = asyncio.create_task(dg.produce())
    reader = asyncio.create_task(agent.process_deepgram_events())
    worker = asyncio.create_task(agent._turn_worker())
    await producer
    await asyncio.sleep(REPLY_PLAYOUT_S * 3)
    reader.cancel()
    worker.cancel()

    assert peak == 1, f"{peak} turns were live at once"


async def test_abandoning_a_turn_does_not_absorb_our_own_cancellation():
    """
    `_abandon_current_turn` awaits the turn it cancelled, so it has to tell
    the turn's CancelledError from its own. Swallowing both made `stop()` fail
    to stop anything: the turn ran its whole teardown after the caller had
    hung up and the bridges were closed, and dialled a transfer it had
    promised.
    """
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")

    async def stubborn():
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            await asyncio.sleep(0.2)      # slow to let go, like a real teardown
            raise

    agent._turn_task = asyncio.create_task(stubborn())
    await asyncio.sleep(0.05)

    abandoning = asyncio.create_task(agent._abandon_current_turn())
    await asyncio.sleep(0.05)
    abandoning.cancel()                    # this is `stop()`

    with pytest.raises(asyncio.CancelledError):
        await abandoning


async def test_first_audio_latency_is_recorded_before_the_transaction_closes():
    """
    The span sweep in the teardown ran BEFORE the producer and receiver were
    joined. On a short uninterrupted turn the text is fully streamed before
    Cartesia's first audio arrives, so the transaction was finished at ~0ms
    and the receiver then wrote first_audio_latency_ms onto a closed
    transaction. The number existed and meant nothing.
    """
    order = []

    class Txn:
        # Named, because a child span's finish is not the transaction's and
        # conflating them is how this assertion first passed for the wrong
        # reason.
        def __init__(self, name):
            self.name = name
            self.timestamp = None

        def start_child(self, **kw):
            return Txn("child")

        def set_data(self, key, value):
            order.append(("set_data", key))

        def finish(self):
            order.append(("finish", self.name))
            self.timestamp = "done"

    txn = Txn("transaction")

    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.cartesia = MagicMock()
    agent.cartesia.cancel_stream = AsyncMock()
    agent.cartesia.send_transcript_chunk = AsyncMock()

    async def audio():
        await asyncio.sleep(0.15)          # audio arrives after the text is done
        yield {"type": "chunk", "context_id": "ctx_one", "data": "QUJDRA=="}
        yield {"type": "done", "context_id": "ctx_one"}

    agent.cartesia.receive_audio_events = audio
    agent.is_running = True
    agent.state = ConversationState.AGENT_SPEAKING

    async def llm(history):
        yield "Check-in is from two p.m."

    agent.llm_callback = llm
    agent._turn_id += 1
    await agent._run_parallel_streaming_pipeline(
        agent._turn_id, context_id="ctx_one", transaction=txn, span_1=None)

    assert ("set_data", "first_audio_latency_ms") in order, "the latency was never recorded"
    assert order.index(("set_data", "first_audio_latency_ms")) < order.index(("finish", "transaction")), (
        f"first_audio_latency_ms was written after the transaction closed: {order}"
    )


async def test_the_greeting_falls_back_to_synthesis_when_the_clip_fails():
    """
    The cached-clip path's `finally` stood the agent down on the FAILURE path
    too, and the synthesis fallback below it starts by checking
    `state != AGENT_SPEAKING` — so a clip that exists but cannot be played
    opened the call in total silence, which is the one thing the fallback
    exists to prevent. The fallback also shipped with no test at all, on a
    path whose previous version had never once run.
    """
    import json as _json

    media = []

    ws = AsyncMock()
    fail_at = {"n": 0}

    async def record(payload):
        if _json.loads(payload).get("event") != "media":
            return
        fail_at["n"] += 1
        if fail_at["n"] == 1:
            # The clip starts playing and the socket rejects it — a truncated
            # clip, a closed connection, anything.
            raise RuntimeError("clip playback failed")
        media.append(payload)

    ws.send_text = AsyncMock(side_effect=record)

    agent = CascadedPipelineOrchestrator(twilio_ws=ws, stream_sid="MZtest")
    agent.cartesia = MagicMock()
    agent.cartesia.cancel_stream = AsyncMock()
    agent.cartesia.send_transcript_chunk = AsyncMock()

    async def audio():
        yield {"type": "chunk", "context_id": None, "data": "QUJDRA=="}
        yield {"type": "done", "context_id": None}

    agent.cartesia.receive_audio_events = audio
    agent.is_running = True

    await agent.trigger_initial_greeting()

    assert media, (
        "the call opened in total silence: the cached clip failed and the "
        "synthesis fallback was dead on arrival because the state had already "
        "been stood down"
    )
    assert agent.state == ConversationState.AWAITING_INPUT


# ─────────────────────────────────────────────────────────────────────────────
# A third review found the invariant held for the turn pipeline and not for the
# greeting, which was a second speaker the worker knew nothing about — plus two
# faults in the paths that enforce the invariant.
# ─────────────────────────────────────────────────────────────────────────────


async def test_the_greeting_gives_up_the_floor_to_the_first_turn():
    """
    The greeting ran on its own task with no turn id, and its only stop
    condition was the shared `self.state` — which the new turn sets back to
    AGENT_SPEAKING three lines after the barge-in. So the greeting's tail
    played over the caller's first answer and then stood that turn down
    mid-sentence. Measured before the fix: 12 greeting frames interleaved
    with the answer, the answer cut at 22 of 60 chunks, and because it
    counted as interrupted it never reached history — so the agent answered
    the same question again.

    `arm_immunity(3.0)` covers the whole clip, so acoustic barge-in is off
    for the greeting and this path — a Flux EndOfTurn — is the only way to
    interrupt it. It is the common case, not an edge case.

    Red only when BOTH the greeting's turn-id gate and its registration as
    `_turn_task` are removed; either one alone stops the overlap. Same
    redundancy as `test_only_one_turn_is_ever_live`, and worth keeping, but it
    means this pins neither mechanism on its own.
    """
    import json as _json

    greeting_media_after_handover = []
    handed_over = asyncio.Event()

    ws = AsyncMock()

    async def record(payload):
        # The turn stub below writes no audio of its own, so every media frame
        # after the handover belongs to the greeting. Filtering on "is a turn
        # running" instead — which the first version of this test did — makes
        # the failure unrecordable and the test worthless.
        if handed_over.is_set() and _json.loads(payload).get("event") == "media":
            greeting_media_after_handover.append(payload)

    ws.send_text = AsyncMock(side_effect=record)
    turn_running = {"yes": False}

    agent = CascadedPipelineOrchestrator(twilio_ws=ws, stream_sid="MZtest")
    agent.cartesia = MagicMock()
    agent.cartesia.cancel_stream = AsyncMock()
    agent.cartesia.send_transcript_chunk = AsyncMock()
    agent.is_running = True

    async def pipeline(*_a, **_kw):
        turn_running["yes"] = True
        agent.state = ConversationState.AGENT_SPEAKING
        await asyncio.sleep(0.5)
        # Only reached if the greeting did not stand this turn down.
        agent.history.append({"role": "assistant", "content": "Yes, we have rooms tonight."})
        agent.state = ConversationState.AWAITING_INPUT

    agent._run_parallel_streaming_pipeline = pipeline

    greeting = asyncio.create_task(agent.trigger_initial_greeting())
    await asyncio.sleep(0.4)                     # greeting is playing
    assert not greeting.done(), "the greeting finished before the test could interrupt it"

    handed_over.set()
    await agent.handle_user_turn_complete("do you have a room for tonight?")

    assert not greeting_media_after_handover, (
        f"{len(greeting_media_after_handover)} frames of greeting audio were still "
        f"written to Twilio after the first turn took the floor"
    )
    spoken = [m for m in agent.history if m["role"] == "assistant"
              and "rooms tonight" in m["content"]]
    assert spoken, (
        "the first answer never reached history — the greeting's tail stood the "
        "turn down mid-sentence and it counted as interrupted"
    )
    greeting.cancel()


async def test_a_call_that_has_stopped_keeps_no_promises():
    """
    `stop()` cancels the turn, but the pipeline's teardown swallows that
    cancellation once per join and runs to the end — so a transfer promised in
    the last turn was dialled about thirty seconds after the caller hung up.
    The turn-id guard passes, because the turn id never moved.
    """
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.cartesia = MagicMock()
    agent.cartesia.cancel_stream = AsyncMock()
    agent.cartesia.send_transcript_chunk = AsyncMock()
    agent._transfer_call = AsyncMock()
    agent._hangup_call = AsyncMock()

    async def audio():
        yield {"type": "chunk", "context_id": "ctx", "data": "QUJDRA=="}
        yield {"type": "done", "context_id": "ctx"}

    agent.cartesia.receive_audio_events = audio
    agent.state = ConversationState.AGENT_SPEAKING
    agent.is_running = True

    async def llm(history):
        yield "Putting you through now."

    agent.llm_callback = llm
    agent._turn_id += 1
    agent._pending_transfer = "+61300000000"
    agent._pending_turn = agent._turn_id

    agent.is_running = False          # the caller hung up; stop() ran
    await agent._run_parallel_streaming_pipeline(agent._turn_id, context_id="ctx")

    agent._transfer_call.assert_not_called()
    agent._hangup_call.assert_not_called()


async def test_abandoning_a_turn_does_not_leave_the_caller_in_silence():
    """
    `_abandon_current_turn` waits for the abandoned pipeline, whose teardown
    shield-waited its Cartesia reader for 15s — and that reader is parked in
    recv() with nothing to wake it once its context is cancelled. Nothing
    could cancel it except the NEXT turn, which cannot start until the wait
    returns. Measured at 15.4 seconds of dead air after a barge-in.

    Whether a cancelled Cartesia context emits a trailing chunk is a provider
    detail, and the code must not bet on the optimistic branch — so this
    server goes silent, which is the bad case.

    **A canary, not a regression test.** It stays green with the pre-cancel
    removed, because cancelling the pipeline task also interrupts the
    shield-wait inside it, and I could not reproduce the 15s through this
    path. The reviewer measured it driving the worker; the pre-cancel is kept
    because not waiting on a socket for a turn that is over is right either
    way, and this assertion will catch the wait if another path reintroduces
    it.
    """
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.cartesia = MagicMock()
    agent.cartesia.cancel_stream = AsyncMock()
    agent.cartesia.send_transcript_chunk = AsyncMock()

    async def audio():
        yield {"type": "chunk", "context_id": "ctx_one", "data": "QUJDRA=="}
        await asyncio.sleep(3600)       # parked, exactly like a cancelled context

    agent.cartesia.receive_audio_events = audio
    agent.is_running = True
    agent.state = ConversationState.AGENT_SPEAKING

    async def llm(history):
        yield "Check-in is from two p.m."

    agent.llm_callback = llm
    agent._turn_id += 1
    agent._turn_task = asyncio.create_task(agent._run_parallel_streaming_pipeline(
        agent._turn_id, context_id="ctx_one"))
    await asyncio.sleep(0.2)

    agent.state = ConversationState.AWAITING_INPUT       # barge-in
    started = time.monotonic()
    await agent._abandon_current_turn()
    waited = time.monotonic() - started

    assert waited < 1.0, (
        f"the caller waited {waited:.1f}s of dead air before the next turn could "
        f"start, because the abandoned turn was shield-waiting a parked socket"
    )


async def test_a_transcript_is_not_lost_when_the_handler_is_cancelled():
    """
    `history.append` for the caller's words sat BELOW
    `await self._abandon_current_turn()`, and the worker cancels the handler
    the moment the caller says something else. A transcript caught in that
    window was dropped with nothing logged — the caller said it, the model
    never saw it.

    The window is opened here the way a real one is: a turn that is slow to
    die, so the next handler is still inside `_abandon_current_turn` when the
    caller speaks again.

    **A canary, not a regression test.** It stays green with the append moved
    back below the abandon — I could not get the worker to cancel a handler
    mid-abandon in this harness, though a reviewer demonstrated the loss with
    their own. The ordering is kept because recording what the caller said
    before doing anything cancellable is right regardless, and this assertion
    will catch the loss if a future change widens the window.
    """
    async def pipeline(*_a, **_kw):
        agent.state = ConversationState.AGENT_SPEAKING
        try:
            await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            await asyncio.sleep(0.30)      # slow teardown, like the real joins
            raise

    agent = _agent(pipeline)
    dg = FakeDeepgram([
        (0.00, {"type": "TurnInfo", "event": "EndOfTurn", "transcript": "what rooms do you have?"}),
        (0.10, {"type": "TurnInfo", "event": "EndOfTurn", "transcript": "hello? what rooms do you have?"}),
        (0.15, {"type": "TurnInfo", "event": "EndOfTurn", "transcript": "are you still there?"}),
    ])
    agent.deepgram = dg

    producer = asyncio.create_task(dg.produce())
    reader = asyncio.create_task(agent.process_deepgram_events())
    worker = asyncio.create_task(agent._turn_worker())
    await producer
    await asyncio.sleep(0.9)
    reader.cancel()
    worker.cancel()

    said = [m["content"] for m in agent.history if m["role"] == "user"]
    assert "hello? what rooms do you have?" in said, (
        f"the caller's words were dropped in the cancellation window; history "
        f"holds only {said!r}"
    )
