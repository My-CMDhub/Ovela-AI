"""
The voice dyno runs every concurrent call's audio on ONE asyncio loop. Any
synchronous network call inside a tool freezes all of them for its duration.

These tests fake the slow network call with a blocking `time.sleep` (the
shape of the real SDK call) and run a ticker task alongside. If the call ran
inline on the loop the ticker would get ~0 ticks; offloaded, it keeps ticking.
"""
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.voice_agent.functions import stripe_handlers
from services.voice_agent.functions import coalcreek_handlers
from services.voice_agent.functions.coalcreek_handlers import CoalCreekFunctionDispatcher

BLOCK_S = 0.4
TICK_S = 0.01


async def _count_ticks_while(coro):
    """Run `coro` while a ticker counts loop iterations; return (result, ticks)."""
    ticks = 0
    stop = asyncio.Event()

    async def ticker():
        nonlocal ticks
        while not stop.is_set():
            await asyncio.sleep(TICK_S)
            ticks += 1

    t = asyncio.create_task(ticker())
    try:
        result = await coro
    finally:
        stop.set()
        await t
    return result, ticks


# ── Stripe ────────────────────────────────────────────────────────────────────

async def test_stripe_checkout_runs_off_the_event_loop(monkeypatch):
    def slow_create(**kwargs):
        time.sleep(BLOCK_S)  # blocking, like the real requests-based SDK call
        return SimpleNamespace(url="https://checkout.test/s", id="cs_test_1")

    monkeypatch.setattr(stripe_handlers, "_STRIPE_CONFIGURED", True)
    monkeypatch.setattr(stripe_handlers.stripe.checkout.Session, "create", slow_create)

    (url, sid), ticks = await _count_ticks_while(
        stripe_handlers.create_checkout_session(amount_aud=150, room_type="queen", booking_ref="CC-1")
    )

    assert (url, sid) == ("https://checkout.test/s", "cs_test_1")
    # Inline this would be 0-1 ticks; offloaded it is ~BLOCK_S / TICK_S (≈40).
    assert ticks >= 10, f"event loop starved during Stripe call ({ticks} ticks)"


async def test_stripe_checkout_still_never_raises(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("stripe down")

    monkeypatch.setattr(stripe_handlers, "_STRIPE_CONFIGURED", True)
    monkeypatch.setattr(stripe_handlers.stripe.checkout.Session, "create", boom)
    assert await stripe_handlers.create_checkout_session(amount_aud=150, room_type="queen") == (None, None)


def test_stripe_http_client_has_short_timeout():
    client = stripe_handlers.stripe.default_http_client
    assert client is not None
    assert getattr(client, "_timeout", None) == stripe_handlers._STRIPE_TIMEOUT_S
    assert stripe_handlers.stripe.max_network_retries <= 1


async def test_cold_path_awaits_async_checkout(monkeypatch):
    fake = AsyncMock(return_value=(None, None))  # "not configured" → early return
    monkeypatch.setattr(stripe_handlers, "create_checkout_session", fake)
    await coalcreek_handlers._handle_stripe_and_guest_email(
        booking_ref="CC-1", room_type="queen", total_amt=150.0,
        guest_email="", guest_name="", guest_phone="",
        check_in="2026-10-10", check_out="2026-10-11", db_service=None,
    )
    fake.assert_awaited_once()


# ── perform_live_search (Gemini grounding) ────────────────────────────────────

class _FakeGenaiClient:
    """Sync path blocks (and is a failure if used); async path yields to the loop."""

    last_config = None
    sync_called = False

    def __init__(self, *args, **kwargs):
        def sync_generate(**kw):
            _FakeGenaiClient.sync_called = True
            time.sleep(BLOCK_S)
            return SimpleNamespace(text="sync answer")

        async def async_generate(**kw):
            _FakeGenaiClient.last_config = kw.get("config")
            await asyncio.sleep(BLOCK_S)
            return SimpleNamespace(text="Sunny, 22 degrees")

        self.models = SimpleNamespace(generate_content=sync_generate)
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=async_generate))


async def test_live_search_uses_async_client_and_keeps_loop_responsive(monkeypatch):
    from google import genai

    _FakeGenaiClient.sync_called = False
    monkeypatch.setattr(genai, "Client", _FakeGenaiClient)

    dispatcher = CoalCreekFunctionDispatcher(
        db_service=MagicMock(), user_phone="+61400000000",
        save_reservation_fn=AsyncMock(), abuse_protection=MagicMock(),
    )
    result, ticks = await _count_ticks_while(
        dispatcher.execute("perform_live_search", {"query": "weather in Coal Creek"})
    )

    assert result == {"success": True, "answer": "Sunny, 22 degrees"}
    assert not _FakeGenaiClient.sync_called, "blocking sync genai client used on the event loop"
    assert ticks >= 10, f"event loop starved during live search ({ticks} ticks)"
    # The 8s per-request timeout must survive the switch to the async client.
    assert _FakeGenaiClient.last_config.http_options.timeout == 8000
