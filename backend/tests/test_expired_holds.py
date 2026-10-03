"""
tests/test_expired_holds.py — a lapsed payment link gives the room back, and
the guest is told so rather than lost.

When a Stripe checkout session expires unpaid, the webhook marks the hold
"expired". Three things have to agree on what that means:

  availability   the room is free again (it was blocking sale forever)
  lookups        the booking is still FOUND, so a caller ringing about it
                 hears "your hold lapsed" instead of "I can't find you"
  resend link    refuses, because a fresh link would take money for a room
                 that may already have been sold to someone else
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.voice_agent.functions.coalcreek_handlers import (
    handle_lookup_booking,
    handle_resend_payment_link,
)

CALLER = "+61499888777"
EXPIRED_HOLD = {
    "$id": "doc1", "booking_reference": "CC-55555", "guest_name": "Ada Lovelace",
    "guest_phone": CALLER, "guest_email": "ada@example.com",
    "room_type": "queen", "room_number": "3",
    "check_in_date": "2030-01-10", "check_out_date": "2030-01-12",
    "total_amount": 240, "status": "expired", "payment_status": "pending_payment",
}


def _db_svc(docs):
    from appwrite.query import Query
    from services.db.bookings import BookingsMixin

    class FakeDb(BookingsMixin):
        motel_db_id = "motel_db_test"

    FakeDb.Query = Query
    svc = FakeDb()
    svc._make_request = AsyncMock(return_value={"documents": docs})
    return svc


async def test_an_expired_hold_no_longer_blocks_the_room():
    live = dict(EXPIRED_HOLD, **{"$id": "doc2", "status": "pending", "room_number": "4"})
    svc = _db_svc([EXPIRED_HOLD, live])
    rows = await svc.get_motel_reservations("2030-01-10", "2030-01-12")
    assert [r["room_number"] for r in rows] == ["4"]


async def test_casing_does_not_keep_an_expired_hold_alive():
    svc = _db_svc([dict(EXPIRED_HOLD, status="Expired")])
    assert await svc.get_motel_reservations("2030-01-10", "2030-01-12") == []


async def test_resend_refuses_to_revive_an_expired_hold():
    db = MagicMock()
    db.lookup_motel_reservation = AsyncMock(return_value=[EXPIRED_HOLD])

    result = await handle_resend_payment_link({"guest_email": "ada@example.com"}, db, CALLER)

    assert result["success"] is False
    assert result.get("hold_expired") is True
    assert "cancelled" in result["error"].lower() and "do not say" in result["error"].lower()


async def test_resend_still_works_for_a_live_hold_next_to_an_expired_one():
    """Same email, an old lapsed hold and a current one: the current one is paid
    for, the old one is not what blocks it."""
    live = dict(EXPIRED_HOLD, **{"$id": "doc2", "booking_reference": "CC-66666",
                                 "status": "pending", "payment_status": "pending_payment"})
    db = MagicMock()
    db.lookup_motel_reservation = AsyncMock(return_value=[EXPIRED_HOLD, live])

    result = await handle_resend_payment_link({"guest_email": "ada@example.com"}, db, CALLER)

    assert result.get("hold_expired") is not True


async def test_lookup_tells_the_agent_the_hold_lapsed_not_that_it_is_on_hold():
    db = MagicMock()
    db.lookup_motel_reservation = AsyncMock(return_value=[EXPIRED_HOLD])

    result = await handle_lookup_booking({"booking_reference": "CC-55555"}, db, CALLER)

    text = str(result)
    assert "EXPIRED" in text
    assert "on hold awaiting payment" not in text
    assert "resend_payment_link" not in text.replace("Do NOT resend the payment link", "")


@pytest.mark.parametrize("status", ["pending", "reserved", "link_sent"])
async def test_live_holds_still_offer_a_resend(status):
    db = MagicMock()
    db.lookup_motel_reservation = AsyncMock(return_value=[dict(EXPIRED_HOLD, status=status)])

    result = await handle_lookup_booking({"booking_reference": "CC-55555"}, db, CALLER)

    assert "EXPIRED" not in str(result)
