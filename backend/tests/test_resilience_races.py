"""
tests/test_resilience_races.py — two interleavings found by review of the
provider-resilience work, each reproduced before it was fixed.

  A reader left parked on a replaced Cartesia socket reported that socket's
  close as a drop, and marked the NEW, open socket dead: the re-synthesis
  the reconnect existed for was then silently muted.

  When Deepgram could not be recovered, the goodbye on a deaf line could be
  cancelled by a turn the worker had already started — the CancelledError
  escaped, the hang-up never ran, and the call stayed open and deaf while the
  orphaned turn went on to answer after the goodbye.
"""

import asyncio
from unittest.mock import AsyncMock, PropertyMock, patch

import services.voice_agent.cascaded_orchestrator as orch_module
from services.voice_agent.bridges.cartesia_standalone import CartesiaStandaloneBridge
from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
from services.voice_agent.vad import ConversationState
from tests.test_provider_resilience import CartesiaServer, _speaking_cartesia


async def test_a_stale_reader_cannot_mark_the_new_socket_dead():
    async with CartesiaServer() as cartesia:
        bridge = CartesiaStandaloneBridge()
        with patch.object(CartesiaStandaloneBridge, "url", new_callable=PropertyMock,
                          return_value=cartesia.url):
            assert await bridge.connect()

            async def read():
                async for _ in bridge.receive_audio_events():
                    pass

            a = asyncio.create_task(read())
            await asyncio.sleep(0.05)
            b = asyncio.create_task(read())          # second reader -> ConcurrencyError
            await asyncio.sleep(0.05)
            assert b.done() and not bridge.is_connected
            assert not a.done(), "reader A is still parked on the old socket"

            assert await bridge.ensure_connected()   # reopens, closes the stale one
            await asyncio.sleep(0.1)
            assert bridge.is_connected, "the stale reader's drop report clobbered the new socket"
            await bridge.close()


async def test_the_deaf_line_goodbye_still_hangs_up_when_a_turn_was_in_flight(monkeypatch):
    monkeypatch.setattr(orch_module, "PLAYBACK_DRAIN_GRACE_S", 0.01)
    monkeypatch.setattr(orch_module, "cognitive_delay", lambda _e: 0)
    twilio = AsyncMock()
    clear_gate = asyncio.Event()

    async def send_text(msg):
        if '"clear"' in msg:
            await clear_gate.wait()           # the barge-in's Twilio clear is slow
    twilio.send_text = send_text

    agent = CascadedPipelineOrchestrator(twilio_ws=twilio, stream_sid="MZtest")
    agent.is_running = True
    agent.call_sid = "CA1"
    agent.cartesia = _speaking_cartesia()
    agent._hangup_call = AsyncMock()
    llm_calls = []

    async def llm(history):
        llm_calls.append(history[-1]["content"])
        yield "Sure, parking is free."
    agent.llm_callback = llm

    # A reply is being spoken when the caller's next turn arrives.
    agent.state = ConversationState.AGENT_SPEAKING
    agent._turn_id = 1
    speaking = asyncio.create_task(asyncio.sleep(3600))
    agent._turn_task = speaking

    agent._turn_worker_task = asyncio.create_task(agent._turn_worker())
    agent._finished_turns.put_nowait("no wait, is parking free?")
    await asyncio.sleep(0.05)   # worker -> handle_user_turn_complete -> barge-in, stuck on clear

    deaf = asyncio.create_task(agent._end_deaf_call())
    await asyncio.sleep(0.05)
    clear_gate.set()
    await asyncio.wait_for(deaf, timeout=5)   # must return, not raise CancelledError
    await asyncio.sleep(0.5)

    assert agent._hangup_call.await_count == 1
    assert llm_calls == [], "the orphaned turn answered after the goodbye"
    speaking.cancel()
