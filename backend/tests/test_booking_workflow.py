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


# ---------------------------------------------------------------------------
# A whole-workflow Appwrite stand-in, for tests that go through the dispatcher
# ---------------------------------------------------------------------------

class WorkflowDb:
    """Rooms + reservation rows. A save becomes a row that later lookups,
    availability reads and patches all see, as in the real collection."""

    def __init__(self, rooms):
        self.rooms = rooms
        self.rows: list[dict] = []
        self.saved: list[dict] = []
        self.patches: list[tuple[str, dict]] = []
        self.lookups = 0

    async def get_motel_rooms(self, tenant_id="coalcreek"):
        return list(self.rooms)

    async def get_motel_reservations(self, start, end, tenant_id="coalcreek"):
        return [dict(r) for r in self.rows
                if r.get("room_number") and r["check_in_date"] < end and r["check_out_date"] > start]

    async def lookup_motel_reservation(self, phone=None, email=None, tenant_id="coalcreek", **_):
        self.lookups += 1
        return [dict(r) for r in self.rows
                if (phone and r.get("guest_phone") == phone) or (email and r.get("guest_email") == email)]

    async def update_motel_reservation(self, booking_id, data):
        self.patches.append((booking_id, dict(data)))
        for r in self.rows:
            if r["$id"] == booking_id:
                r.update(data)
        return {"$id": booking_id}

    async def save(self, data):
        doc = dict(data, **{"$id": f"doc{len(self.saved) + 1}"})
        self.saved.append(doc)
        self.rows.append(doc)
        return {"success": True, "document": {"$id": doc["$id"]}}


def _booking_args(ci=FRI, co=SUN, room="queen", email="guest@example.com", name="Test Guest") -> dict:
    return {
        "guest_name": name, "check_in_date": ci, "check_out_date": co,
        "room_type": room, "num_guests": 1, "guest_email": email,
        "has_user_confirmed_summary": "YES",
    }


def _dispatcher(db) -> "ch.CoalCreekFunctionDispatcher":
    return ch.CoalCreekFunctionDispatcher(db, CALLER, db.save, abuse_protection=None)


# ---------------------------------------------------------------------------
# 7. The payment link goes to the address that was saved
# ---------------------------------------------------------------------------

class TestLinkGoesToTheSavedAddress:

    async def test_spoken_email_is_sent_in_its_normalised_form(self, stripe_calls):
        db = WorkflowDb([_room("1")])

        result = await _dispatcher(db).execute(
            "create_booking_request", _booking_args(email="james at g mail dot com"))

        assert result["success"] is True
        assert db.saved[0]["guest_email"] == "james@gmail.com"
        assert [c["guest_email"] for c in stripe_calls] == ["james@gmail.com"]


# ---------------------------------------------------------------------------
# 2. A tool that fails after writing still drops the per-call reservation memo
# ---------------------------------------------------------------------------

class TestRetryAfterAFailedWriteDoesNotDoubleBook:
    """The retry's own duplicate check is the idempotency key (same caller,
    check-in and room type in one call → patch). It only works if it reads
    the row the failed attempt wrote, not the memo from before it."""

    async def test_retry_after_a_timeout_patches_the_first_hold(self, monkeypatch):
        db = WorkflowDb([_room("1"), _room("2")])
        disp = _dispatcher(db)
        monkeypatch.setattr(disp, "TOOL_TIMEOUT_S", 0.2)
        hang = asyncio.Event()

        async def email_never_confirms(**kw):
            await hang.wait()  # SMTP stalls: the dispatcher's 6 s wait outlives the tool budget

        monkeypatch.setattr(ch, "_handle_stripe_and_guest_email", email_never_confirms)

        first = await disp.execute("create_booking_request", _booking_args())
        assert first["success"] is False          # what the model sees: a failure
        assert len(db.saved) == 1                 # what happened: a hold was written

        async def email_ok(**kw):
            if kw.get("notify_event") is not None:
                kw["notify_result"][0] = True
                kw["notify_event"].set()

        monkeypatch.setattr(ch, "_handle_stripe_and_guest_email", email_ok)
        second = await disp.execute("create_booking_request", _booking_args())
        hang.set()

        assert second["success"] is True
        assert len(db.saved) == 1, "the retry created a second hold"
        assert second["booking_reference"] == db.saved[0]["booking_reference"]

    async def test_retry_after_an_exception_patches_the_first_hold(self, monkeypatch, stripe_calls):
        db = WorkflowDb([_room("1"), _room("2")])
        disp = _dispatcher(db)

        def stripe_down(**kw):  # raises after the hold is saved
            raise RuntimeError("stripe import failed")

        monkeypatch.setattr(ch, "_handle_stripe_and_guest_email", stripe_down)
        first = await disp.execute("create_booking_request", _booking_args())
        assert "error" in first
        assert len(db.saved) == 1

        async def email_ok(**kw):
            if kw.get("notify_event") is not None:
                kw["notify_result"][0] = True
                kw["notify_event"].set()

        monkeypatch.setattr(ch, "_handle_stripe_and_guest_email", email_ok)
        second = await disp.execute("create_booking_request", _booking_args())

        assert second["success"] is True
        assert len(db.saved) == 1, "the retry created a second hold"

    async def test_read_only_tools_keep_the_memo(self, stripe_calls):
        db = WorkflowDb([_room("1")])
        disp = _dispatcher(db)

        await disp.execute("lookup_booking", {"guest_phone": CALLER})
        before = db.lookups
        assert before > 0
        await disp.execute("lookup_booking", {"guest_phone": CALLER})

        assert db.lookups == before


# ---------------------------------------------------------------------------
# 4. The price quoted is the price charged
# ---------------------------------------------------------------------------

class TestQuotedPriceIsChargedPrice:

    async def _quote_then_book(self, db, stripe_calls):
        disp = _dispatcher(db)
        quote = await disp.execute(
            "check_availability", {"check_in_date": FRI, "check_out_date": SUN, "room_type": "queen"})
        booked = await disp.execute("create_booking_request", _booking_args())
        return quote, booked

    async def test_db_base_rate_is_quoted_and_charged(self, stripe_calls):
        db = WorkflowDb([_room("1", rate=120)])

        quote, booked = await self._quote_then_book(db, stripe_calls)

        assert quote["price_per_night"] == 120 and quote["total"] == 240
        assert db.saved[0]["rate_per_night"] == 120
        assert db.saved[0]["total_amount"] == 240
        assert booked["total_amount"] == 240
        assert stripe_calls[0]["total_amt"] == 240

    async def test_room_without_base_rate_uses_the_kb_price_for_both(self, stripe_calls):
        """No base_rate: both sides fall back to the KB price the prompt lists,
        not a $150 the quote invented and the booking never charged."""
        from services.knowledge_base.coalcreek import COALCREEK_DATA
        kb = COALCREEK_DATA["rooms"]["queen"]["price"]
        db = WorkflowDb([_room("1", rate=None)])

        quote, booked = await self._quote_then_book(db, stripe_calls)

        assert quote["price_per_night"] == kb
        assert db.saved[0]["total_amount"] == kb * 2
        assert stripe_calls[0]["total_amt"] == kb * 2
