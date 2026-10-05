"""
tests/test_booking_workflow.py — the booking workflow across tool calls.

Each class pins one bug from the booking-workflow audit. All offline: the
fakes stand in for Appwrite, Stripe and SMTP, so these run in the normal suite.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from services.voice_agent.functions import coalcreek_handlers as ch

CALLER = "+61499888777"


def _day(n: int) -> str:
    """n days from today (Melbourne) — never rots into the past."""
    today = datetime.now(ZoneInfo("Australia/Melbourne")).date()
    return (today + timedelta(days=n)).isoformat()


FRI, SAT, SUN, MON = _day(10), _day(11), _day(12), _day(13)


@pytest.fixture(autouse=True)
def pms_mode(monkeypatch):
    from core import config as _cfg
    monkeypatch.setattr(_cfg.settings, "USE_LIVE_SCRAPING", False)


@pytest.fixture
def stripe_calls(monkeypatch):
    """Record every Stripe/email dispatch instead of performing it."""
    calls: list[dict] = []

    async def fake(**kw):
        calls.append(kw)
        if kw.get("notify_result") is not None:
            kw["notify_result"][0] = True
        if kw.get("notify_event") is not None:
            kw["notify_event"].set()

    monkeypatch.setattr(ch, "_handle_stripe_and_guest_email", fake)
    return calls


# ---------------------------------------------------------------------------
# 1. An empty payment_status is not "unpaid"
# ---------------------------------------------------------------------------

CONFIRMED_WALK_IN = {
    "$id": "walkin1", "booking_reference": "CC-WALK01", "guest_name": "Ada Lovelace",
    "guest_phone": CALLER, "guest_email": "ada@example.com", "room_type": "Double Room",
    "check_in_date": FRI, "check_out_date": SAT, "total_amount": 135,
    "status": "confirmed", "payment_status": "",
}


class TestEmptyPaymentStatusIsNotPending:

    async def test_giving_a_name_does_not_reopen_a_confirmed_walk_in(self, stripe_calls):
        db = MagicMock()
        db.lookup_motel_reservation = AsyncMock(return_value=[dict(CONFIRMED_WALK_IN)])
        db.update_motel_reservation = AsyncMock()

        result = await ch.handle_update_guest_info({"guest_name": "Ada Lovelace"}, db, user_phone=CALLER)

        assert result["success"] is True
        db.update_motel_reservation.assert_not_awaited()
        assert stripe_calls == []

    async def test_resend_link_refuses_a_confirmed_walk_in(self, stripe_calls):
        db = MagicMock()
        db.lookup_motel_reservation = AsyncMock(return_value=[dict(CONFIRMED_WALK_IN)])

        result = await ch.handle_resend_payment_link({"guest_email": "ada@example.com"}, db, CALLER)

        assert result["success"] is False
        assert stripe_calls == []

    @pytest.mark.parametrize("status", ["reserved", "pending", "pending_payment", "link_sent"])
    async def test_a_hold_with_no_payment_status_yet_still_gets_its_link(self, stripe_calls, status):
        """A fresh hold has no payment_status until its link goes out — the
        status alone has to be enough for those."""
        doc = dict(CONFIRMED_WALK_IN, status=status)
        db = MagicMock()
        db.lookup_motel_reservation = AsyncMock(return_value=[doc])

        result = await ch.handle_resend_payment_link({"guest_email": "ada@example.com"}, db, CALLER)

        assert result["success"] is True
        assert len(stripe_calls) == 1

    async def test_legacy_confirmed_but_unpaid_row_still_gets_its_link(self, stripe_calls):
        """Rows written `confirmed` before payment (see the N6 guard) say so in
        payment_status; those keep working."""
        doc = dict(CONFIRMED_WALK_IN, payment_status="pending_payment")
        db = MagicMock()
        db.lookup_motel_reservation = AsyncMock(return_value=[doc])

        result = await ch.handle_resend_payment_link({"guest_email": "ada@example.com"}, db, CALLER)

        assert result["success"] is True
        assert len(stripe_calls) == 1


# ---------------------------------------------------------------------------
# 5. A failed availability check is not remembered for the rest of the call
# ---------------------------------------------------------------------------

def _room(num: str, rtype: str = "queen", rate=120) -> dict:
    return {"room_number": num, "room_type": rtype, "status": "available", "base_rate": rate}


class FlakyMotelDb:
    """Fails the first `fail_reads` reservation reads, then answers."""

    def __init__(self, rooms, fail_reads=0):
        self.rooms = rooms
        self.fail_reads = fail_reads
        self.reads = 0

    async def get_motel_rooms(self, tenant_id="coalcreek"):
        return list(self.rooms)

    async def get_motel_reservations(self, start, end, tenant_id="coalcreek"):
        self.reads += 1
        if self.reads <= self.fail_reads:
            return None  # "couldn't read" — the contract get_motel_reservations keeps
        return []


class TestFailedAvailabilityIsNotCached:
    ARGS = {"check_in_date": FRI, "check_out_date": SUN, "room_type": "queen"}

    async def test_a_retry_after_a_failed_read_asks_the_calendar_again(self):
        db = FlakyMotelDb([_room("1")], fail_reads=1)
        ctx = {"availability_cache": {}}

        first = await ch.handle_check_availability(dict(self.ARGS), db, context=ctx)
        second = await ch.handle_check_availability(dict(self.ARGS), db, context=ctx)

        assert first["available"] == "unknown"
        assert second["available"] is True
        assert db.reads == 2

    async def test_a_retry_after_an_exception_asks_the_calendar_again(self, monkeypatch):
        db = FlakyMotelDb([_room("1")])
        ctx = {"availability_cache": {}}
        real = ch._check_appwrite_availability
        calls = {"n": 0}

        async def boom_once(*a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("unexpected")
            return await real(*a, **kw)

        monkeypatch.setattr(ch, "_check_appwrite_availability", boom_once)

        first = await ch.handle_check_availability(dict(self.ARGS), db, context=ctx)
        second = await ch.handle_check_availability(dict(self.ARGS), db, context=ctx)

        assert first["available"] == "unknown"
        assert second["available"] is True

    async def test_a_real_answer_is_still_cached(self):
        db = FlakyMotelDb([_room("1")])
        ctx = {"availability_cache": {}}

        await ch.handle_check_availability(dict(self.ARGS), db, context=ctx)
        await ch.handle_check_availability(dict(self.ARGS), db, context=ctx)

        assert db.reads == 1
