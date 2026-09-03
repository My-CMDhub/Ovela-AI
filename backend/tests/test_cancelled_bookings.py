"""
tests/test_cancelled_bookings.py — a cancelled booking is not a booking.

get_motel_reservations already drops cancelled and rejected rows before the
availability check sees them, which is why cancelling a test booking puts the
room back on sale. The identity lookups did not do the same, so a cancelled row
went on answering the phone — and ordered newest-first, it answered BEFORE the
live reservation on the same number.

Found by accident and then measured: a cancelled test booking on the owner's
handset took the identity eval from 24/28 with zero wrong-person answers to
21/28 with three. Confidently returning the wrong guest is the worst failure
this system has, and a row nobody thought was still in play caused it.

In production the shape is: a guest cancels, rings back a week later, and is
read the booking they cancelled as though it were live.
"""

import pytest
from unittest.mock import AsyncMock



CANCELLED = {"$id": "1", "booking_reference": "CC-DEAD", "guest_name": "Ghost Guest",
             "guest_phone": "+61400000001", "guest_email": "ghost@example.com",
             "status": "cancelled", "created_at": "2026-09-03T02:33:43"}
REJECTED = dict(CANCELLED, **{"$id": "2", "booking_reference": "CC-NOPE",
                              "status": "rejected"})
LIVE = {"$id": "3", "booking_reference": "CC-76818", "guest_name": "Dhruv Patel",
        "guest_phone": "+61400000001", "guest_email": "dhruv@example.com",
        "status": "confirmed", "created_at": "2026-08-31T05:31:06"}


def _service():
    from services.appwrite import db_service
    return db_service


def _filter(docs):
    """The filter is a module-level function, not a method: the lookup wraps
    everything in a broad `except` that returns [], so an unbound attribute
    would be a silent "no booking found" rather than a crash — which is exactly
    what the first version of it was."""
    from services.db.bookings import _live_only
    return _live_only(docs)


class TestTheFilterItself:
    def test_cancelled_and_rejected_are_dropped(self):
        assert _filter([CANCELLED, LIVE, REJECTED]) == [LIVE]

    def test_a_live_booking_survives(self):
        assert _filter([LIVE]) == [LIVE]

    def test_a_missing_status_is_treated_as_live(self):
        """Appwrite stores absent values as None. A booking with no status is a
        pipeline glitch, and refusing to find it would be worse than finding
        it — this is the one direction where being permissive is safer."""
        no_status = dict(LIVE, status=None)
        assert _filter([no_status]) == [no_status]

    def test_case_does_not_matter(self):
        assert _filter([dict(CANCELLED, status="Cancelled")]) == []

    def test_nothing_in_nothing_out(self):
        assert _filter([]) == []
        assert _filter(None) == []


class TestTheLookupPaths:
    """All four ways in have to agree. The phone path is the one that broke,
    because it is the one the caller preload uses on every single call."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kwargs", [
        {"phone": "+61400000001"},
        {"booking_reference": "CC-DEAD"},
        {"email": "ghost@example.com"},
    ])
    async def test_a_cancelled_booking_is_never_returned(self, monkeypatch, kwargs):
        svc = _service()
        monkeypatch.setattr(svc, "_motel_request",
                            AsyncMock(return_value={"documents": [CANCELLED]}))
        monkeypatch.setattr(svc, "_recent_reservations", AsyncMock(return_value=[]))

        assert await svc.lookup_motel_reservation(tenant_id="coalcreek", **kwargs) == []

    @pytest.mark.asyncio
    async def test_the_live_booking_still_wins_when_both_exist(self, monkeypatch):
        """The real regression: the cancelled row was NEWER, so ordered
        newest-first it was returned and the live one never seen."""
        svc = _service()
        monkeypatch.setattr(svc, "_motel_request",
                            AsyncMock(return_value={"documents": [CANCELLED, LIVE]}))

        found = await svc.lookup_motel_reservation(phone="+61400000001",
                                                   tenant_id="coalcreek")

        assert [d["booking_reference"] for d in found] == ["CC-76818"]

    @pytest.mark.asyncio
    async def test_the_fuzzy_name_roster_excludes_them_too(self, monkeypatch):
        """Name matching scores against this roster. A cancelled guest left in
        it can win a spoken-name match against a live one."""
        svc = _service()
        monkeypatch.setattr(svc, "_motel_request",
                            AsyncMock(return_value={"documents": [CANCELLED, LIVE]}))

        roster = await svc._recent_reservations(None)

        assert [d["booking_reference"] for d in roster] == ["CC-76818"]
