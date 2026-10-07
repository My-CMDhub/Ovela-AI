"""
tests/test_overtake_teardown.py — a caller who overtakes a reply is answered
at once, not after 15 seconds of silence.

When the caller says something new while a reply is still being generated,
the turn worker cancels the old turn before the new turn's barge-in has moved
the state on. The old pipeline's teardown then still believed it held the
floor, and shield-waited up to 15 s for a Cartesia `done` that a cancelled
context may never send. Found by review; present since the turn worker.
"""

import asyncio
import time

import services.voice_agent.cascaded_orchestrator as orch
from tests.test_speculative_eot import Call, FakeOpenAI, last_user, text, until


def _long_or_short(messages):
    if "long" in last_user(messages):
        return [text(f"Sentence number {i}. ") for i in range(40)]
    return [text("Yes, "), text("parking is free.")]


class _Slow:
    """Each event after the first arrives 20 ms apart, like a real stream."""

    def __init__(self, inner):
        self.inner = inner

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.inner.started:
            await asyncio.sleep(0.02)
        return await self.inner.__anext__()

    async def aclose(self):
        await self.inner.aclose()


async def test_an_overtaken_reply_does_not_hold_the_line(monkeypatch):
    monkeypatch.setattr(orch, "PLAYBACK_DRAIN_GRACE_S", 0.01)
    monkeypatch.setattr(orch, "cognitive_delay", lambda _e: 0)
    monkeypatch.setattr(orch, "get_coalcreek_prompt", lambda _d, _t: "You are the receptionist.")
    monkeypatch.setattr(orch.settings, "SPECULATIVE_EOT_ENABLED", False)

    llm = FakeOpenAI(responder=_long_or_short)
    create = llm.create

    async def slow_create(**kw):
        return _Slow(await create(**kw))

    async with Call(llm, flag=None) as call:
        call.agent._openai.chat.completions.create = slow_create
        call.dg.send("EndOfTurn", "tell me something long")
        await asyncio.sleep(0.05)
        overtaken_at = time.monotonic()
        call.dg.send("EndOfTurn", "actually do you have parking")

        await until(lambda: any("parking is free" in s for s in call.agent.cartesia.spoken), 3.0)
        assert time.monotonic() - overtaken_at < 2.0
