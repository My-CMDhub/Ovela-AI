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
