"""
tests/test_provider_resilience.py
=================================
What a live call does when one of its providers goes away mid-call.

Before these fixes every one of them failed quietly and for good:

- Cartesia's socket drops: every later turn ran the model, synthesised
  nothing, and the unspoken reply went into history and the transcript as if
  the caller had heard it.
- Deepgram's socket drops: the event loop simply ended and the call was deaf
  until the caller hung up.
- OpenAI stalls: no deadline at all (SDK default 600 s, two retries), and the
  error path promised "I am checking those details right now" — a promise
  nothing ever kept.

The Cartesia tests run the real bridge against a real `websockets` server,
for the reason given in test_turn_pipelining: at a provider boundary a mock
tests our assumption, not their contract.
"""

import asyncio
import json
import logging
import time
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
import websockets

import services.voice_agent.cascaded_orchestrator as orch_module
from services.voice_agent.bridges.cartesia_standalone import CartesiaStandaloneBridge
from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
from services.voice_agent.vad import ConversationState


@pytest.fixture(autouse=True)
def _fast_playback(monkeypatch):
    # The drain grace is network slack for a real phone line; here it is only
    # time spent waiting, and no pacing delay before the first phrase.
    monkeypatch.setattr(orch_module, "PLAYBACK_DRAIN_GRACE_S", 0.05)
    monkeypatch.setattr(orch_module, "cognitive_delay", lambda _elapsed: 0)


# ─────────────────────────────────────────────────────────────────────────────
# A. Cartesia
# ─────────────────────────────────────────────────────────────────────────────

class CartesiaServer:
    """
    A Cartesia that speaks: one chunk per transcript, `done` when a context is
    closed. `drop_first_on_message` makes the first connection die the moment
    it is asked to speak — the mid-turn drop.
    """

    def __init__(self, drop_first_on_message: bool = False):
        self.drop_first_on_message = drop_first_on_message
        self.connections = []          # server-side sockets, in order
        self.received = []             # (connection number, message)
        self.server = None

    async def handler(self, ws):
        self.connections.append(ws)
        number = len(self.connections)
        async for raw in ws:
            msg = json.loads(raw)
            self.received.append((number, msg))
            if number == 1 and self.drop_first_on_message:
                await ws.close(code=1011, reason="internal error")
                return
            if msg.get("transcript"):
                await ws.send(json.dumps({
                    "type": "chunk", "context_id": msg["context_id"], "data": "QUJDRA==",
                }))
            if msg.get("continue") is False:
                await ws.send(json.dumps({"type": "done", "context_id": msg["context_id"]}))

    async def __aenter__(self):
        self.server = await websockets.serve(self.handler, "127.0.0.1", 0)
        port = self.server.sockets[0].getsockname()[1]
        self.url = f"ws://127.0.0.1:{port}"
        return self

    async def __aexit__(self, *exc):
        self.server.close()
        await self.server.wait_closed()


def _agent_with(bridge) -> CascadedPipelineOrchestrator:
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.cartesia = bridge
    agent.is_running = True
    return agent


async def _turn(agent, said: str, reply: str, context_id: str) -> None:
    """One whole turn through the real pipeline: model text -> TTS -> Twilio."""
    agent.history.append({"role": "user", "content": said})

    async def llm(_history):
        for token in reply.split(" "):
            yield token + " "

    agent.llm_callback = llm
    agent.state = ConversationState.AGENT_SPEAKING
    agent.current_context_id = context_id
    agent._turn_id += 1
    await asyncio.wait_for(
        agent._run_parallel_streaming_pipeline(agent._turn_id, context_id=context_id),
        timeout=10,
    )


def _media_sent(agent) -> int:
    return sum(1 for c in agent.twilio_ws.send_text.await_args_list
               if '"media"' in c.args[0])


async def test_after_a_cartesia_drop_the_next_turn_reconnects_and_is_heard():
    async with CartesiaServer() as cartesia:
        bridge = CartesiaStandaloneBridge()
        with patch.object(CartesiaStandaloneBridge, "url", new_callable=PropertyMock,
                          return_value=cartesia.url):
            assert await bridge.connect()
            agent = _agent_with(bridge)
            try:
                await _turn(agent, "hi", "Hello, how can I help?", "ctx_one")
                assert _media_sent(agent) > 0

                # The socket dies between turns, while nothing is reading it —
                # the case the old code only discovered by losing a phrase.
                await cartesia.connections[0].close(code=1011)
                await asyncio.sleep(0.1)

                before = _media_sent(agent)
                await _turn(agent, "do you allow pets?", "Yes, small dogs are welcome.", "ctx_two")

                assert len(cartesia.connections) == 2, "the dropped socket was never reopened"
                assert _media_sent(agent) > before, "the turn after the drop reached the caller not at all"
                assert agent.history[-1] == {"role": "assistant", "content": "Yes, small dogs are welcome."}
                assert bridge.is_connected
            finally:
                await bridge.close()


async def test_a_dead_cartesia_that_cannot_reconnect_is_not_recorded_as_spoken(caplog):
    async with CartesiaServer() as cartesia:
        bridge = CartesiaStandaloneBridge()
        with patch.object(CartesiaStandaloneBridge, "url", new_callable=PropertyMock,
                          return_value=cartesia.url):
            assert await bridge.connect()
            agent = _agent_with(bridge)
            # Cartesia is gone and stays gone: the socket is dropped and every
            # reconnect is refused.
            await cartesia.connections[0].close(code=1011)
            cartesia.server.close()
            await cartesia.server.wait_closed()
            await asyncio.sleep(0.1)

            with caplog.at_level(logging.WARNING), \
                    patch.object(orch_module.sentry_sdk, "capture_message") as sentry:
                await _turn(agent, "what time is check-in?", "Check-in is from 2 p.m.", "ctx_dead")

            assert agent.history == [{"role": "user", "content": "what time is check-in?"}], (
                "a reply the caller never heard went into history as spoken — the model "
                "will build its next answer on words that were never said"
            )
            assert agent._silent_turns == 1
            errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
            assert any("produced no audio" in r.getMessage() for r in errors)
            assert any("Dropping" in r.getMessage() for r in caplog.records
                       if r.levelno == logging.WARNING), "the dropped send left no trace"
            assert any("no audio" in str(c.args[0]) for c in sentry.call_args_list)
            await bridge.close()


async def test_a_mid_turn_drop_is_resynthesised_once_on_a_fresh_socket():
    async with CartesiaServer(drop_first_on_message=True) as cartesia:
        bridge = CartesiaStandaloneBridge()
        with patch.object(CartesiaStandaloneBridge, "url", new_callable=PropertyMock,
                          return_value=cartesia.url):
            assert await bridge.connect()
            agent = _agent_with(bridge)
            try:
                await _turn(agent, "hi", "We have queen rooms. Breakfast is included.", "ctx_mid")
            finally:
                await bridge.close()

        retried = [m for n, m in cartesia.received if n == 2]
        assert [m["context_id"] for m in retried] == ["ctx_mid_retry"], retried
        assert retried[0]["transcript"] == "We have queen rooms. Breakfast is included."
        assert retried[0]["continue"] is False
        assert _media_sent(agent) > 0, "the retry reached the caller not at all"
        assert agent.history[-1]["content"] == "We have queen rooms. Breakfast is included."
        assert agent._silent_turns == 0


async def test_ensure_connected_never_races_two_connects():
    bridge = CartesiaStandaloneBridge()
    bridge.ws = MagicMock()           # a socket existed and has died
    bridge.is_connected = False
    connects = 0

    async def slow_connect():
        nonlocal connects
        connects += 1
        await asyncio.sleep(0.05)
        bridge.ws = MagicMock()
        bridge.is_connected = True
        return True

    bridge.connect = slow_connect
    results = await asyncio.gather(bridge.ensure_connected(), bridge.ensure_connected())
    assert results == [True, True]
    assert connects == 1, "two callers opened two sockets; one reader is now on the wrong one"


async def test_ensure_connected_does_not_reopen_a_socket_closed_by_stop():
    bridge = CartesiaStandaloneBridge()
    bridge.ws = MagicMock(close=AsyncMock())
    bridge.connect = AsyncMock(return_value=True)
    await bridge.close()
    assert await bridge.ensure_connected() is False
    bridge.connect.assert_not_awaited()


# ─────────────────────────────────────────────────────────────────────────────
# B. Deepgram
# ─────────────────────────────────────────────────────────────────────────────

class DroppableDeepgram:
    """
    Deepgram's shape: one socket at a time, read by one consumer, which ends
    when the socket closes. Each successful `connect()` is a fresh socket.
    `connect_results` scripts the reconnects (True/False), default success;
    `flap` makes every new socket die as soon as it opens.
    """

    def __init__(self, connect_results=None, flap=False):
        self.socket: asyncio.Queue = asyncio.Queue()
        self.connect_results = list(connect_results or [])
        self.flap = flap
        self.connects = 0
        self.readers = 0
        self.close = AsyncMock()
        self.send_audio = AsyncMock()

    async def receive_events(self):
        socket = self.socket
        self.readers += 1
        assert self.readers == 1, "two readers on one Deepgram socket"
        try:
            while True:
                event = await socket.get()
                if event is None:
                    return              # the socket closed
                yield event
        finally:
            self.readers -= 1

    async def connect(self):
        self.connects += 1
        ok = self.connect_results.pop(0) if self.connect_results else True
        if ok:
            self.socket = asyncio.Queue()
            if self.flap:
                self.socket.put_nowait(None)
        return ok

    def drop(self):
        self.socket.put_nowait(None)

    def say(self, transcript):
        self.socket.put_nowait({"type": "TurnInfo", "event": "EndOfTurn", "transcript": transcript})


@pytest.fixture
def fast_stt_backoff(monkeypatch):
    monkeypatch.setattr(orch_module, "STT_RECONNECT_BACKOFF_S", (0.01,) * 5)


def _speaking_cartesia():
    cartesia = MagicMock()
    cartesia.ensure_connected = AsyncMock(return_value=True)
    cartesia.send_transcript_chunk = AsyncMock()
    cartesia.cancel_stream = AsyncMock()
    cartesia.close = AsyncMock()
    cartesia.is_connected = True

    async def audio():
        yield {"type": "chunk", "data": "QUJDRA=="}
        yield {"type": "done"}

    cartesia.receive_audio_events = audio
    return cartesia


async def _until(condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition never became true"
        await asyncio.sleep(0.01)


async def test_a_deepgram_drop_mid_call_reconnects_and_later_turns_are_heard(fast_stt_backoff):
    handled = []

    async def pipeline(*_a, **_kw):
        handled.append(agent.history[-1]["content"])
        agent.state = ConversationState.AWAITING_INPUT

    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.is_running = True
    agent._run_parallel_streaming_pipeline = pipeline
    agent.deepgram = dg = DroppableDeepgram()

    reader = asyncio.create_task(agent.process_deepgram_events())
    worker = asyncio.create_task(agent._turn_worker())
    try:
        with patch.object(orch_module.sentry_sdk, "capture_message") as sentry:
            dg.say("what rooms do you have?")
            await _until(lambda: handled == ["what rooms do you have?"])

            dg.drop()
            await _until(lambda: dg.connects == 1)
            dg.say("and the price?")
            await _until(lambda: len(handled) == 2)

        assert handled == ["what rooms do you have?", "and the price?"]
        assert not reader.done(), "the read loop ended — the call is deaf again"
        assert any("reconnected" in str(c.args[0]) for c in sentry.call_args_list)
    finally:
        reader.cancel()
        worker.cancel()


async def test_an_event_the_loop_cannot_handle_is_recovered_like_a_drop(fast_stt_backoff):
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.is_running = True
    agent.deepgram = dg = DroppableDeepgram()

    reader = asyncio.create_task(agent.process_deepgram_events())
    try:
        dg.socket.put_nowait(["not", "a", "dict"])       # .get() raises on this
        await _until(lambda: dg.connects == 1)
        dg.say("are you there?")
        await _until(lambda: not agent._finished_turns.empty())
        assert agent._finished_turns.get_nowait() == "are you there?"
        dg.close.assert_awaited()                       # the old socket, before the new
    finally:
        reader.cancel()


async def test_deepgram_that_never_comes_back_ends_the_call_politely(fast_stt_backoff):
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.is_running = True
    agent.call_sid = "CA1"
    agent.cartesia = _speaking_cartesia()
    agent._hangup_call = AsyncMock()
    agent.deepgram = dg = DroppableDeepgram(connect_results=[False] * 10)
    agent._turn_worker_task = asyncio.create_task(agent._turn_worker())

    reader = asyncio.create_task(agent.process_deepgram_events())
    dg.drop()
    # Returns, rather than raising out of the Deepgram task.
    await asyncio.wait_for(reader, timeout=10)

    assert dg.connects == len(orch_module.STT_RECONNECT_BACKOFF_S)
    spoken = [c.kwargs["transcript"] for c in agent.cartesia.send_transcript_chunk.await_args_list]
    assert any("can't hear you" in t for t in spoken), f"the caller was not told: {spoken}"
    agent._hangup_call.assert_awaited_once()
    assert agent.is_running is False
    assert agent._turn_worker_task.done()


async def test_a_socket_that_keeps_dying_is_given_up_on(fast_stt_backoff):
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.is_running = True
    agent.cartesia = _speaking_cartesia()
    agent._hangup_call = AsyncMock()
    agent.deepgram = dg = DroppableDeepgram(flap=True)

    reader = asyncio.create_task(agent.process_deepgram_events())
    dg.drop()
    await asyncio.wait_for(reader, timeout=10)

    assert dg.connects == orch_module.STT_MAX_SHORT_LIVED
    agent._hangup_call.assert_awaited_once()


async def test_stop_during_the_reconnect_backoff_exits_promptly(monkeypatch):
    monkeypatch.setattr(orch_module, "STT_RECONNECT_BACKOFF_S", (5.0,) * 5)
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.is_running = True
    agent.cartesia = _speaking_cartesia()
    agent._hangup_call = AsyncMock()
    agent.deepgram = dg = DroppableDeepgram()

    reader = asyncio.create_task(agent.process_deepgram_events())
    dg.drop()
    await asyncio.sleep(0.05)               # inside the first 5 s backoff

    started = time.monotonic()
    await agent.stop()
    await asyncio.wait_for(reader, timeout=1.0)

    assert time.monotonic() - started < 0.5, "the reconnect slept out its backoff after stop()"
    assert dg.connects == 0, "a socket was reopened for a call that had ended"
    agent._hangup_call.assert_not_awaited()


# ─────────────────────────────────────────────────────────────────────────────
# C. OpenAI
# ─────────────────────────────────────────────────────────────────────────────

FIRST_TOKEN_S = 0.1
GAP_S = 0.1


@pytest.fixture
def tight_llm_deadlines(monkeypatch):
    monkeypatch.setattr(orch_module.settings, "LLM_FIRST_TOKEN_TIMEOUT_S", FIRST_TOKEN_S)
    monkeypatch.setattr(orch_module.settings, "LLM_STREAM_GAP_TIMEOUT_S", GAP_S)
    monkeypatch.setattr(orch_module.settings, "LLM_FALLBACK_MODEL", "")


def _delta(content=None, tool_calls=None):
    ev = MagicMock()
    ev.choices = [MagicMock()]
    ev.choices[0].delta.content = content
    ev.choices[0].delta.tool_calls = tool_calls
    return ev


def _tool_delta(name, arguments):
    tc = MagicMock()
    tc.index, tc.id = 0, "call_0"
    tc.function.name = name
    tc.function.arguments = arguments
    return _delta(tool_calls=[tc])


async def _never(*_a, **_kw):
    await asyncio.Event().wait()        # OpenAI accepted the request and went quiet
    yield _delta(content="too late")


def _llm_agent(*rounds, model="gpt-4.1-nano", options=None):
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.is_running = True
    agent._context_ready = True
    agent.tenant_config = {"voice_settings": {"llm_model": model, **(options or {})}}
    agent.dispatcher = MagicMock(caller_reservation=AsyncMock(return_value=[]))
    agent.dispatcher.execute = AsyncMock(return_value={"ok": True})
    agent._openai = MagicMock()
    agent._openai.chat.completions.create = AsyncMock(side_effect=[r() for r in rounds])
    return agent


async def _reply(agent, said="do you have a queen room friday?"):
    return [c async for c in agent._default_llm_callback([{"role": "user", "content": said}])]


async def test_no_first_token_retries_once_then_says_so_honestly(tight_llm_deadlines):
    agent = _llm_agent(_never, _never)
    started = time.monotonic()
    chunks = await asyncio.wait_for(_reply(agent), timeout=5)
    elapsed = time.monotonic() - started

    assert agent._openai.chat.completions.create.await_count == 2, "no retry, or more than one"
    assert "".join(chunks).strip() == orch_module.LLM_TROUBLE_LINE
    assert "checking those details" not in "".join(chunks)
    assert elapsed < 2 * FIRST_TOKEN_S + 0.5, f"took {elapsed:.2f}s — the deadline does not bound the turn"


async def test_the_retry_answers_when_the_first_attempt_hangs(tight_llm_deadlines):
    async def answers(*_a, **_kw):
        yield _delta(content="Yes, a queen is free on Friday.")

    agent = _llm_agent(_never, answers)
    assert await _reply(agent) == ["Yes, a queen is free on Friday."]


async def test_the_retry_uses_the_fallback_model_without_the_first_models_options(
        tight_llm_deadlines, monkeypatch):
    monkeypatch.setattr(orch_module.settings, "LLM_FALLBACK_MODEL", "gpt-4.1-nano")

    async def answers(*_a, **_kw):
        yield _delta(content="Yes.")

    agent = _llm_agent(_never, answers, model="gpt-5.6-luna",
                       options={"reasoning_effort": "none"})
    assert await _reply(agent) == ["Yes."]
    first, retry = (c.kwargs for c in agent._openai.chat.completions.create.await_args_list)
    assert first["model"] == "gpt-5.6-luna" and first["reasoning_effort"] == "none"
    assert retry["model"] == "gpt-4.1-nano"
    assert "reasoning_effort" not in retry, "nano rejects reasoning_effort — the retry would 400"


async def test_a_stall_mid_reply_ends_with_the_honest_line(tight_llm_deadlines):
    async def stalls(*_a, **_kw):
        yield _delta(content="We have a queen room")
        await asyncio.Event().wait()
        yield _delta(content=" for you.")

    agent = _llm_agent(stalls)
    started = time.monotonic()
    chunks = await asyncio.wait_for(_reply(agent), timeout=5)

    assert chunks == ["We have a queen room", ".", " " + orch_module.LLM_TROUBLE_LINE]
    assert time.monotonic() - started < GAP_S + 0.5


async def test_a_stall_inside_a_tool_call_never_runs_the_truncated_call(tight_llm_deadlines):
    async def stalls_mid_tool(*_a, **_kw):
        yield _tool_delta("create_booking_request", '{"guest_name": "Ja')
        await asyncio.Event().wait()
        yield _tool_delta("create_booking_request", 'ne"}')

    agent = _llm_agent(stalls_mid_tool)
    chunks = await asyncio.wait_for(_reply(agent), timeout=5)

    agent.dispatcher.execute.assert_not_awaited()
    assert agent._tools_called == []
    assert chunks[-1] == " " + orch_module.LLM_TROUBLE_LINE


async def test_a_normal_fast_stream_is_untouched(tight_llm_deadlines):
    async def fast(*_a, **_kw):
        for part in ("Hello! ", "How can I help today?"):
            await asyncio.sleep(GAP_S / 4)
            yield _delta(content=part)

    agent = _llm_agent(fast)
    assert await _reply(agent) == ["Hello! ", "How can I help today?"]
    assert agent._openai.chat.completions.create.await_count == 1


async def test_the_openai_client_has_explicit_limits():
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.warm_llm_on_start = False
    with patch("services.appwrite.db_service") as db, \
            patch("services.voice_agent.abuse_protection.AbuseProtection"), \
            patch("services.voice_agent.memory.CallerMemoryBank"), \
            patch("services.voice_agent.functions.CoalCreekFunctionDispatcher"), \
            patch("openai.AsyncOpenAI") as client:
        db.get_tenant_config = AsyncMock(return_value={})
        await agent._build_call_context()

    kwargs = client.call_args.kwargs
    assert kwargs["max_retries"] == 1
    timeout = kwargs["timeout"]
    assert timeout.connect <= 5 and timeout.read <= 20, timeout
