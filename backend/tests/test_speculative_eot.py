"""
tests/test_speculative_eot.py
=============================
The speculative first round: on Deepgram Flux's EagerEndOfTurn the model is
asked before the turn is confirmed, and its answer is kept only if EndOfTurn
confirms the same words and the request is still byte-identical.

Driven end to end where it matters — a scripted Deepgram socket, the real read
loop, the real turn worker, the real `_default_llm_callback` and pipeline —
with a fake OpenAI whose streams record whether they were closed, and a fake
Cartesia that records every phrase it was asked to speak.

What must hold, in order of how badly it would go wrong on a call:
  - flag off: nothing at all changes
  - a speculation never speaks, never writes history or call_state, never runs
    a tool before EndOfTurn
  - every speculation that is not used has its stream closed, and none
    outlives stop()
  - when used, exactly one request was made and the caller hears its answer
    sooner by about the eager->final gap
"""

import asyncio
import copy
import enum
import logging
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import services.voice_agent.cascaded_orchestrator as orch_module
from services.voice_agent.call_state import CallState
from services.voice_agent.cascaded_orchestrator import (
    CascadedPipelineOrchestrator,
    normalise_transcript,
)
from services.voice_agent.vad import ConversationState


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(orch_module, "PLAYBACK_DRAIN_GRACE_S", 0.01)
    monkeypatch.setattr(orch_module, "cognitive_delay", lambda _elapsed: 0)
    monkeypatch.setattr(orch_module.settings, "LLM_FIRST_TOKEN_TIMEOUT_S", 6.0)
    monkeypatch.setattr(orch_module.settings, "LLM_STREAM_GAP_TIMEOUT_S", 10.0)
    monkeypatch.setattr(orch_module.settings, "LLM_FALLBACK_MODEL", "")
    monkeypatch.setattr(orch_module.settings, "SPECULATIVE_EOT_ENABLED", False)
    # The real prompt carries the time to the minute; a minute ticking over
    # mid-test would (correctly) change the request and fail a match.
    monkeypatch.setattr(orch_module, "get_coalcreek_prompt", lambda _d, _t: "You are the receptionist.")


# ─────────────────────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────────────────────

def text(content):
    return SimpleNamespace(usage=None, service_tier=None, choices=[
        SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=None))])


def tool(name, arguments):
    call = SimpleNamespace(index=0, id="call_0",
                           function=SimpleNamespace(name=name, arguments=arguments))
    return SimpleNamespace(usage=None, service_tier=None, choices=[
        SimpleNamespace(delta=SimpleNamespace(content=None, tool_calls=[call]))])


STALL = object()


class FakeStream:
    """An OpenAI stream: headers come back at once, the first event after
    `first_token_s`, the rest as fast as they are read."""

    def __init__(self, events, first_token_s):
        self.events = list(events)
        self.first_token_s = first_token_s
        self.started = False
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.started:
            self.started = True
            await asyncio.sleep(self.first_token_s)
        if self.closed or not self.events:
            raise StopAsyncIteration
        event = self.events.pop(0)
        if event is STALL:
            await asyncio.Event().wait()
        return event

    async def aclose(self):
        self.closed = True


def last_user(messages):
    return next(m["content"] for m in reversed(messages) if m["role"] == "user")


def answer_what_was_asked(messages):
    """Replies with the words it was asked, so the test can see which request
    the caller ended up hearing."""
    if messages[-1]["role"] == "tool":
        return [text("Good news, "), text("we have a queen room.")]
    return [text("Sure, "), text(f"you asked {normalise_transcript(last_user(messages))}.")]


class FakeOpenAI:
    def __init__(self, responder=answer_what_was_asked, first_token_s=0.0, fail_first=False):
        self.responder = responder
        self.first_token_s = first_token_s
        self.fail_first = fail_first
        self.requests = []
        self.streams = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.fail_first and len(self.requests) == 1:
            raise RuntimeError("upstream 500")
        stream = FakeStream(self.responder(kwargs["messages"]), self.first_token_s)
        self.streams.append(stream)
        return stream


class FakeCartesia:
    """One chunk of audio per phrase, `done` when the context closes."""

    def __init__(self):
        self.spoken = []
        self.spoken_at = []
        self.events: asyncio.Queue = asyncio.Queue()
        self.is_connected = True
        self.cancel_stream = AsyncMock()
        self.close = AsyncMock()

    async def ensure_connected(self):
        return True

    async def send_transcript_chunk(self, context_id, transcript, continue_stream):
        if transcript:
            self.spoken.append(transcript)
            self.spoken_at.append(time.monotonic())
            await self.events.put({"type": "chunk", "context_id": context_id, "data": "QUJDRA=="})
        if not continue_stream:
            await self.events.put({"type": "done", "context_id": context_id})

    async def receive_audio_events(self):
        while True:
            yield await self.events.get()


class FakeDeepgram:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.close = AsyncMock()
        self.send_audio = AsyncMock()

    async def receive_events(self):
        while True:
            event = await self.queue.get()
            if event is None:
                return
            yield event

    def send(self, kind, transcript=None):
        event = {"type": "TurnInfo", "event": kind}
        if transcript is not None:
            event["transcript"] = transcript
        self.queue.put_nowait(event)


GREETING = "Hello! Thanks for calling Coal Creek. How can I help you today?"


class Call:
    """An orchestrator mid-call, between turns, with its read loop and worker
    running against the fakes above."""

    def __init__(self, llm: FakeOpenAI, flag=True):
        agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
        agent.is_running = True
        agent._context_ready = True
        voice = {"llm_model": "gpt-4.1-nano"}
        if flag is not None:
            voice["speculative_eot"] = flag
        agent.tenant_config = {"voice_settings": voice}
        agent.dispatcher = MagicMock(caller_reservation=AsyncMock(return_value=[]))
        agent.dispatcher.execute = AsyncMock(return_value={"success": True, "available": True})
        agent._openai = MagicMock()
        agent._openai.chat.completions.create = llm.create
        agent.cartesia = FakeCartesia()
        agent.deepgram = FakeDeepgram()
        agent._save_transcript = AsyncMock()
        agent.history = [{"role": "assistant", "content": GREETING}]
        agent.state = ConversationState.AWAITING_INPUT
        self.agent, self.llm, self.dg = agent, llm, agent.deepgram
        self.reader = self.worker = None

    async def __aenter__(self):
        self.reader = asyncio.create_task(self.agent.process_deepgram_events())
        self.agent._turn_worker_task = asyncio.create_task(self.agent._turn_worker())
        return self

    async def __aexit__(self, *exc):
        await self.agent.stop()
        self.reader.cancel()
        try:
            await self.reader
        except (asyncio.CancelledError, Exception):
            pass

    @property
    def spec(self):
        return self.agent._speculation

    async def settle(self):
        await until(lambda: self.dg.queue.empty())
        await asyncio.sleep(0.02)

    async def turn_done(self, timeout=3.0):
        await until(lambda: self.agent.state == ConversationState.AWAITING_INPUT
                    and any(m["role"] == "user" for m in self.agent.history)
                    and self.agent.history[-1]["role"] == "assistant", timeout)


async def until(condition, timeout=3.0):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition never became true"
        await asyncio.sleep(0.005)


def media_sent(agent) -> int:
    return sum(1 for c in agent.twilio_ws.send_text.await_args_list if '"media"' in c.args[0])


def plain_state(agent) -> dict:
    """Every attribute of the orchestrator that is plain data, deep-copied."""
    keep = (bool, int, float, str, list, dict, tuple, type(None), enum.Enum, CallState)
    return {k: copy.deepcopy(v) for k, v in vars(agent).items() if isinstance(v, keep)}


def said(call) -> str:
    return call.agent.history[-1]["content"]


def speculative_tasks():
    return [t for t in asyncio.all_tasks()
            if not t.done() and "_speculate" in repr(t.get_coro())]


# ─────────────────────────────────────────────────────────────────────────────
# Off
# ─────────────────────────────────────────────────────────────────────────────

async def test_flag_off_the_eager_branch_only_logs_and_changes_nothing(caplog):
    llm = FakeOpenAI()
    async with Call(llm, flag=None) as call:
        before = plain_state(call.agent)
        tasks_before = len(asyncio.all_tasks())
        with caplog.at_level(logging.INFO):
            call.dg.send("EagerEndOfTurn", "do you have a queen room?")
            await call.settle()
            call.dg.send("TurnResumed")
            await call.settle()

        assert llm.requests == [], "an LLM request was made with the flag off"
        assert plain_state(call.agent) == before, "the eager branch changed state with the flag off"
        assert len(asyncio.all_tasks()) == tasks_before, "the eager branch started a task"
        assert any("Pre-warming LLM" in r.getMessage() for r in caplog.records)
        assert not any("Speculative" in r.getMessage() for r in caplog.records)

        # And the turn itself is the ordinary one: one request, on EndOfTurn.
        call.dg.send("EndOfTurn", "do you have a queen room friday?")
        await call.turn_done()
        assert len(llm.requests) == 1
        assert last_user(llm.requests[0]["messages"]) == "do you have a queen room friday?"
        assert call.agent._speculation_stats["started"] == 0


async def test_flag_comes_from_settings_unless_the_tenant_overrides_it(monkeypatch):
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    assert agent._speculation_enabled() is False
    monkeypatch.setattr(orch_module.settings, "SPECULATIVE_EOT_ENABLED", True)
    assert agent._speculation_enabled() is True
    agent.tenant_config = {"voice_settings": {"speculative_eot": "false"}}
    assert agent._speculation_enabled() is False
    monkeypatch.setattr(orch_module.settings, "SPECULATIVE_EOT_ENABLED", False)
    agent.tenant_config = {"voice_settings": {"speculative_eot": True}}
    assert agent._speculation_enabled() is True


def test_transcripts_match_on_words_not_punctuation():
    assert normalise_transcript("Yes, that's  right.") == normalise_transcript("yes that's right")
    assert normalise_transcript("A room, for Friday.") == normalise_transcript("a room for friday")
    assert normalise_transcript("Do you have a room?") != normalise_transcript("Do you have a room on Friday?")


@pytest.mark.parametrize("eager, final", [
    ("we'll", "well"),
    ("we're open", "were open"),
    ("$40", "40"),
    ("4.5", "4 5"),
    ("j.smith@gmail.com", "j smith gmail com"),
])
def test_different_words_never_match(eager, final):
    """Found in review: stripping every mark matched these, and the model then
    answered words the caller did not finally say."""
    assert normalise_transcript(eager) != normalise_transcript(final)


# ─────────────────────────────────────────────────────────────────────────────
# Discarded
# ─────────────────────────────────────────────────────────────────────────────

async def test_eager_then_resumed_cancels_with_no_history_change_and_no_audio():
    llm = FakeOpenAI()
    async with Call(llm) as call:
        history = copy.deepcopy(call.agent.history)
        state = copy.deepcopy(call.agent.call_state)
        # A spelled email: the one kind of words hear_caller WOULD keep.
        call.dg.send("EagerEndOfTurn", "my email is j o h n at gmail dot com")
        await until(lambda: call.spec and call.spec.ready.is_set())
        spec = call.spec

        call.dg.send("TurnResumed")
        await call.settle()

        assert spec.discarded and spec.task.done()
        assert llm.streams[0].closed, "the abandoned request's stream was left open"
        assert call.agent.history == history
        assert call.agent.call_state == state, "speculation wrote to call_state"
        assert call.agent.cartesia.spoken == [] and media_sent(call.agent) == 0
        assert call.agent._speculation_stats["discard_reasons"] == {"resumed": 1}


async def test_eager_then_a_different_endofturn_discards_and_asks_again():
    llm = FakeOpenAI()
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "do you have a queen room")
        await until(lambda: call.spec and call.spec.ready.is_set())
        call.dg.send("EndOfTurn", "do you have a queen room on friday")
        await call.turn_done()

        assert len(llm.requests) == 2
        assert llm.streams[0].closed
        assert last_user(llm.requests[1]["messages"]) == "do you have a queen room on friday"
        assert said(call) == "Sure, you asked do you have a queen room on friday."
        assert call.agent._speculation_stats["discard_reasons"] == {"different words": 1}
        assert call.agent._speculation_stats["used"] == 0


@pytest.mark.parametrize("change", ["history", "call_state"])
async def test_a_request_that_changed_since_the_speculation_is_not_reused(change):
    llm = FakeOpenAI()
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "what time is check in")
        await until(lambda: call.spec and call.spec.ready.is_set())
        # Same words confirmed, but the call moved on underneath: a note was
        # added to history, or a tool result changed what call_state says.
        if change == "history":
            call.agent.history.append({"role": "system", "content": "The transfer failed."})
        else:
            call.agent.call_state.reservation_on_file = True
        call.dg.send("EndOfTurn", "What time is check in?")
        await call.turn_done()

        assert len(llm.requests) == 2, "the stale speculative answer was used"
        assert llm.streams[0].closed
        assert call.agent._speculation_stats["discard_reasons"] == {"request changed": 1}


async def test_a_second_eager_replaces_the_first():
    llm = FakeOpenAI()
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "do you have")
        await until(lambda: call.spec and call.spec.ready.is_set())
        first = call.spec
        call.dg.send("EagerEndOfTurn", "do you have parking")
        await until(lambda: call.spec is not first and call.spec and call.spec.ready.is_set())
        assert first.discarded and llm.streams[0].closed

        call.dg.send("EndOfTurn", "Do you have parking?")
        await call.turn_done()
        assert len(llm.requests) == 2, "the confirmed turn asked again instead of using the second"
        assert said(call) == "Sure, you asked do you have parking."
        stats = call.agent._speculation_stats
        assert (stats["started"], stats["used"], stats["discarded"]) == (2, 1, 1)


async def test_barge_in_during_a_speculation_cancels_it():
    llm = FakeOpenAI(first_token_s=5.0)
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "is breakfast included")
        await until(lambda: call.spec is not None and llm.streams)
        spec = call.spec
        # Something took the floor meanwhile and the caller talks over it.
        call.agent.state = ConversationState.AGENT_SPEAKING
        await call.agent.trigger_barge_in(reason="sustained_speech")
        await asyncio.sleep(0.02)

        assert spec.discarded and spec.task.done()
        assert llm.streams[0].closed, "a stream cancelled before its first event was left open"
        assert call.agent._speculation is None


async def test_stop_cancels_a_speculation_and_leaks_no_task():
    llm = FakeOpenAI(first_token_s=5.0)
    call = Call(llm)
    await call.__aenter__()
    call.dg.send("EagerEndOfTurn", "how much is a twin room")
    await until(lambda: call.spec is not None and llm.streams)
    spec = call.spec
    await call.__aexit__(None, None, None)

    assert spec.task.done() and spec.discarded
    assert llm.streams[0].closed
    assert speculative_tasks() == []
    assert call.agent._speculation_stats["discard_reasons"] == {"call ended": 1}


async def test_a_claimed_speculation_is_closed_when_its_turn_is_overtaken():
    """Claimed by a confirmed turn and still waiting for its first token when
    the caller says something else: the turn is cancelled, and the stream it
    was waiting on must go with it — no Deepgram event will come for it."""
    llm = FakeOpenAI(first_token_s=5.0)
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "do you have a room")
        await until(lambda: call.spec is not None and llm.streams)
        spec = call.spec
        call.dg.send("EndOfTurn", "Do you have a room?")
        await until(lambda: call.agent._claimed_speculation is spec)
        call.dg.send("EndOfTurn", "sorry, for two people")
        await until(lambda: spec.discarded)
        await until(lambda: spec.task.done())

        assert llm.streams[0].closed
        assert call.agent._speculation_stats["discard_reasons"] == {"unused": 1}
    assert speculative_tasks() == []


async def test_no_speculation_while_the_agent_is_speaking():
    """Words heard over the agent will cut it (and rewrite history) or be
    held as a backchannel: an answer to them cannot be used, so none is
    bought."""
    llm = FakeOpenAI()
    async with Call(llm) as call:
        call.agent.state = ConversationState.AGENT_SPEAKING
        call.dg.send("EagerEndOfTurn", "mhmm")
        await call.settle()
        assert llm.requests == [] and call.spec is None


# ─────────────────────────────────────────────────────────────────────────────
# Used
# ─────────────────────────────────────────────────────────────────────────────

async def test_confirmed_speculation_is_what_gets_spoken_from_one_request(caplog):
    llm = FakeOpenAI()
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "do you allow pets")
        await until(lambda: call.spec and call.spec.ready.is_set())
        assert call.agent.history == [{"role": "assistant", "content": GREETING}]
        assert call.agent.cartesia.spoken == []

        with caplog.at_level(logging.INFO):
            call.dg.send("EndOfTurn", "Do you allow pets?")
            await call.turn_done()

        assert len(llm.requests) == 1, "the confirmed turn made its own request anyway"
        assert call.agent.history[-2:] == [
            {"role": "user", "content": "Do you allow pets?"},
            {"role": "assistant", "content": "Sure, you asked do you allow pets."},
        ]
        assert "allow pets" in " ".join(call.agent.cartesia.spoken)
        assert media_sent(call.agent) > 0
        stats = call.agent._speculation_stats
        assert (stats["started"], stats["used"], stats["discarded"]) == (1, 1, 0)
        assert any("Speculative first round used" in r.getMessage() and "saved ~" in r.getMessage()
                   for r in caplog.records)


async def test_a_speculative_tool_call_runs_once_and_only_after_endofturn():
    def wants_a_tool(messages):
        if messages[-1]["role"] == "tool":
            return [text("Good news, "), text("we have a queen room.")]
        return [tool("check_availability", '{"check_in_date": "2026-10-09"}')]

    llm = FakeOpenAI(responder=wants_a_tool)
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "is there a room next friday")
        await until(lambda: call.spec and call.spec.ready.is_set())
        await asyncio.sleep(0.05)
        call.agent.dispatcher.execute.assert_not_awaited()
        assert call.agent._tools_called == []
        assert call.agent.cartesia.spoken == [], "the tool acknowledgement was spoken before EndOfTurn"

        call.dg.send("EndOfTurn", "Is there a room next Friday?")
        await call.turn_done()

        call.agent.dispatcher.execute.assert_awaited_once()
        assert call.agent._tools_called == ["check_availability"]
        assert len(llm.requests) == 2          # round 1 (speculative) + round 2 (tool result)
        assert llm.requests[1]["messages"][-1]["role"] == "tool"
        assert "we have a queen room" in " ".join(call.agent.cartesia.spoken)


async def test_a_speculation_that_failed_before_endofturn_costs_nothing():
    llm = FakeOpenAI(fail_first=True)
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "do you have wifi")
        await until(lambda: call.spec and call.spec.ready.is_set())
        call.dg.send("EndOfTurn", "Do you have wifi?")
        await call.turn_done()

        assert len(llm.requests) == 2
        assert said(call) == "Sure, you asked do you have wifi."
        assert call.agent._speculation_stats["discard_reasons"] == {"failed before EndOfTurn": 1}


# ─────────────────────────────────────────────────────────────────────────────
# Deadlines
# ─────────────────────────────────────────────────────────────────────────────

async def test_first_token_deadline_runs_from_the_speculative_request(monkeypatch):
    """Still waiting at EndOfTurn: the speculation's own deadline and single
    retry decide, from when IT asked — never a fresh pair of deadlines on top."""
    deadline = 0.3
    monkeypatch.setattr(orch_module.settings, "LLM_FIRST_TOKEN_TIMEOUT_S", deadline)
    llm = FakeOpenAI(first_token_s=60)
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "can i bring my dog")
        await until(lambda: call.spec is not None and llm.streams)
        await asyncio.sleep(0.2)
        eot = time.monotonic()
        call.dg.send("EndOfTurn", "Can I bring my dog?")
        await until(lambda: any(orch_module.LLM_TROUBLE_LINE.split(",")[0] in s
                                for s in call.agent.cartesia.spoken), timeout=3)
        waited = time.monotonic() - eot

        assert len(llm.requests) == 2, "attempt + one retry, all inside the speculation"
        assert waited < 2 * deadline, f"{waited:.2f}s: deadlines restarted at EndOfTurn"
        assert all(s.closed for s in llm.streams)


async def test_a_first_token_in_hand_has_met_the_deadline(monkeypatch):
    """However long Flux takes to confirm, a speculation that already has its
    first event is not timed out for the wait."""
    monkeypatch.setattr(orch_module.settings, "LLM_FIRST_TOKEN_TIMEOUT_S", 0.1)
    llm = FakeOpenAI()
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "is there a pool")
        await until(lambda: call.spec and call.spec.ready.is_set())
        await asyncio.sleep(0.3)                    # three deadlines' worth
        call.dg.send("EndOfTurn", "Is there a pool?")
        await call.turn_done()

        assert len(llm.requests) == 1
        assert said(call) == "Sure, you asked is there a pool."


async def test_gap_deadline_applies_to_an_adopted_stream(monkeypatch):
    gap = 0.2
    monkeypatch.setattr(orch_module.settings, "LLM_STREAM_GAP_TIMEOUT_S", gap)
    llm = FakeOpenAI(responder=lambda _m: [text("We have a queen room "), STALL])
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "what rooms do you have")
        await until(lambda: call.spec and call.spec.ready.is_set())
        eot = time.monotonic()
        call.dg.send("EndOfTurn", "what rooms do you have")
        await call.turn_done()

        assert time.monotonic() - eot < gap + 0.5
        assert len(llm.requests) == 1
        assert call.agent.history[-1]["content"].endswith(orch_module.LLM_TROUBLE_LINE)


# ─────────────────────────────────────────────────────────────────────────────
# The point of it
# ─────────────────────────────────────────────────────────────────────────────

FIRST_TOKEN_S = 0.30
EAGER_TO_FINAL_S = 0.20


async def _first_audio_after_endofturn(flag: bool) -> float:
    llm = FakeOpenAI(first_token_s=FIRST_TOKEN_S)
    async with Call(llm, flag=flag) as call:
        call.dg.send("EagerEndOfTurn", "is parking free")
        await asyncio.sleep(EAGER_TO_FINAL_S)
        eot = time.monotonic()
        call.dg.send("EndOfTurn", "Is parking free?")
        await call.turn_done()
        assert len(llm.requests) == 1
        return call.agent.cartesia.spoken_at[0] - eot


async def test_endofturn_to_first_token_drops_by_the_eager_gap():
    without = await _first_audio_after_endofturn(flag=False)
    with_spec = await _first_audio_after_endofturn(flag=True)
    saved = without - with_spec

    assert without >= FIRST_TOKEN_S - 0.02
    assert EAGER_TO_FINAL_S - 0.06 <= saved <= EAGER_TO_FINAL_S + 0.06, (
        f"EndOfTurn -> first phrase: {without * 1000:.0f} ms without, "
        f"{with_spec * 1000:.0f} ms with — saved {saved * 1000:.0f} ms"
    )


async def test_counters_reach_the_saved_call_record():
    llm = FakeOpenAI()
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "hi")
        await until(lambda: call.spec and call.spec.ready.is_set())
        call.dg.send("TurnResumed")
        call.dg.send("EagerEndOfTurn", "hi is breakfast included")
        await call.settle()
        call.dg.send("EndOfTurn", "Hi, is breakfast included?")
        await call.turn_done()
        del call.agent._save_transcript             # the real one, this time
        with patch("services.appwrite.db_service") as db:
            db.save_call_transcript = AsyncMock()
            await call.agent._save_transcript()

    meta = db.save_call_transcript.await_args.kwargs["metadata"]
    assert meta["speculation"]["started"] == 2
    assert meta["speculation"]["used"] == 1
    assert meta["speculation"]["discarded"] == 1
    assert meta["speculation"]["discard_reasons"] == {"resumed": 1}


async def test_the_same_words_proposed_twice_are_asked_once():
    """Found in review: every EagerEndOfTurn replaced the speculation, so Flux
    proposing the same words twice paid for the same request twice."""
    llm = FakeOpenAI()
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "is there a spa room")
        await until(lambda: call.spec and call.spec.ready.is_set())
        call.dg.send("EagerEndOfTurn", "Is there a spa room.")
        await call.settle()
        call.dg.send("EndOfTurn", "Is there a spa room?")
        await call.turn_done()

        assert len(llm.requests) == 1
        assert call.agent._speculation_stats["started"] == 1


async def test_an_unclaimed_speculation_that_times_out_pages_nobody(monkeypatch):
    """Found in review: a guess the caller talked past raised an error-level
    Sentry alert for a turn that never happened."""
    monkeypatch.setattr(orch_module.settings, "LLM_FIRST_TOKEN_TIMEOUT_S", 0.1)
    alerts = []
    monkeypatch.setattr(orch_module.sentry_sdk, "capture_message",
                        lambda msg, level=None: alerts.append((level, msg)))
    llm = FakeOpenAI(first_token_s=60)
    async with Call(llm) as call:
        call.dg.send("EagerEndOfTurn", "and the")
        await asyncio.sleep(0.35)             # both attempts miss, nobody has claimed it
        call.dg.send("TurnResumed")
        await call.settle()

    assert not [a for a in alerts if "first-token deadline" in a[1]]
