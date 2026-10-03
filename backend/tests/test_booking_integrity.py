"""
tests/test_booking_integrity.py — a room is sold once, for the whole stay.

Three ways the PMS-mode (Appwrite) booking path could hand out a room it did
not have:

1. Per-type, not per-room, availability. A type counted as free if SOME room of
   it was free each night, and the booking took night 1's room. Room 1 free
   Friday but booked Saturday, room 2 free both: "available", room 1 assigned,
   Saturday double-booked.
2. Fail-open reads. get_motel_reservations turned an Appwrite error into [],
   so an outage made every room look free and the booking assigned one.
3. Check-then-write race. Two calls on one process could both read the last
   room free and both save it.

All offline: the fake below stands in for the Appwrite service.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from services.voice_agent.functions import coalcreek_handlers as ch


def _day(n: int) -> str:
    """n days from today (Melbourne) — never rots into the past."""
    today = datetime.now(ZoneInfo("Australia/Melbourne")).date()
    return (today + timedelta(days=n)).isoformat()


FRI, SAT, SUN = _day(10), _day(11), _day(12)


def _room(num: str, rtype: str = "queen", rate: int = 120) -> dict:
    return {"room_number": num, "room_type": rtype, "status": "available", "base_rate": rate}


def _res(room: str, ci: str, co: str) -> dict:
    return {"room_number": room, "check_in_date": ci, "check_out_date": co, "status": "reserved"}


class FakeMotelDb:
    """Appwrite stand-in. Saves land in `reservations`, so a later check sees
    them, as the real collection would. `save_delay` yields to the loop
    mid-save, which is where an unlocked second caller would slip in."""

    def __init__(self, rooms, reservations=None, unreadable=False, save_delay=0.0):
        self.rooms = rooms
        self.reservations = list(reservations or [])
        self.unreadable = unreadable
        self.save_delay = save_delay
        self.saved: list[dict] = []

    async def get_motel_rooms(self, tenant_id="coalcreek"):
        return list(self.rooms)

    async def get_motel_reservations(self, start, end, tenant_id="coalcreek"):
        await asyncio.sleep(0)  # a real read yields; let racers interleave
        if self.unreadable:
            return None
        return [r for r in self.reservations
                if r["check_in_date"] < end and r["check_out_date"] > start]

    async def lookup_motel_reservation(self, **kwargs):
        return []  # no existing hold to patch

    async def save(self, data):
        await asyncio.sleep(self.save_delay)
        self.saved.append(dict(data))
        if data.get("room_number"):
            self.reservations.append(_res(data["room_number"], data["check_in_date"], data["check_out_date"]))
        return {"success": True, "document": {"$id": f"doc{len(self.saved)}"}}


@pytest.fixture(autouse=True)
def pms_mode(monkeypatch):
    from core import config as _cfg
    monkeypatch.setattr(_cfg.settings, "USE_LIVE_SCRAPING", False)


def _booking_args(ci=FRI, co=SUN, room="queen", name="Test Guest") -> dict:
    return {
        "guest_name": name,
        "check_in_date": ci,
        "check_out_date": co,
        "room_type": room,
        "num_guests": 1,
        "guest_email": "guest@example.com",
        "has_user_confirmed_summary": True,
    }


async def _book(db: FakeMotelDb, **kw) -> dict:
    return await ch.handle_create_booking_request(
        args=_booking_args(**kw), user_phone="+61400000000",
        save_reservation_fn=db.save, db_service=db,
    )


# ---------------------------------------------------------------------------
# 1. Availability is per room, across every night
# ---------------------------------------------------------------------------

class TestOneRoomForTheWholeStay:

    async def test_room_taken_on_night_two_is_not_the_one_assigned(self):
        """The audit's exact case: room 1 free Fri, booked Sat; room 2 free both."""
        db = FakeMotelDb([_room("1"), _room("2")], [_res("1", SAT, SUN)])

        result = await _book(db)

        assert result["success"] is True
        assert db.saved[0]["room_number"] == "2"
        assert db.saved[0]["status"] == "reserved"

    async def test_the_quoted_night_one_room_is_the_assignable_one(self):
        """per_night_results keeps its shape, but its night-1 sample for a type
        must be a room free all nights, so a quoted price is a real room's."""
        db = FakeMotelDb([_room("1", rate=100), _room("2", rate=140)], [_res("1", SAT, SUN)])

        res = await ch._check_appwrite_availability(db, FRI, SUN)

        assert res["success"] is True
        assert res["available_all_nights"] is True
        assert res["available_rooms"] == ["Double Room"]
        assert [r["room_number"] for r in res["rooms_free_all_nights"]["Double Room"]] == ["2"]
        night1 = res["per_night_results"][FRI]
        assert [(r["room_type"], r["room_number"], r["price_per_night"]) for r in night1] == [
            ("Double Room", "2", 140)
        ]

    async def test_type_unavailable_when_no_single_room_spans_the_stay(self):
        """Each night has a Double free — never the same one. Not bookable."""
        db = FakeMotelDb([_room("1"), _room("2")], [_res("1", SAT, SUN), _res("2", FRI, SAT)])

        res = await ch._check_appwrite_availability(db, FRI, SUN, "Double Room")
        assert res["success"] is True
        assert res["available_all_nights"] is False
        assert "Double Room" not in res["available_rooms"]
        assert res["blocked_dates"] == []  # no night is sold out on its own
        # Per-night view is still reported truthfully.
        assert [r["room_number"] for r in res["per_night_results"][FRI]] == ["1"]
        assert [r["room_number"] for r in res["per_night_results"][SAT]] == ["2"]

        result = await _book(db)
        assert result["success"] is False
        assert "no longer available" in result["message"]
        assert db.saved == []

    async def test_check_availability_says_no_and_does_not_read_out_an_empty_date(self):
        db = FakeMotelDb([_room("1"), _room("2")], [_res("1", SAT, SUN), _res("2", FRI, SAT)])

        out = await ch.handle_check_availability(
            {"check_in_date": FRI, "check_out_date": SUN, "room_type": "queen"}, db)

        assert out["available"] is False
        assert "sold out on ." not in out["ai_should_say"]
        assert "one room free for the whole stay" in out["ai_should_say"]

    async def test_check_availability_names_the_types_own_blocked_night(self):
        """Twin free both nights, Double sold out Saturday: the Double's blocked
        night is Saturday, even though the motel as a whole is not full."""
        db = FakeMotelDb([_room("1"), _room("5", "twin")], [_res("1", SAT, SUN)])

        out = await ch.handle_check_availability(
            {"check_in_date": FRI, "check_out_date": SUN, "room_type": "queen"}, db)

        assert out["available"] is False
        assert out["blocked_dates"] == [SAT]


# ---------------------------------------------------------------------------
# 2. A failed read is "unknown", never "empty"
# ---------------------------------------------------------------------------

class TestAvailabilityFailsClosed:

    async def test_unreadable_reservations_is_not_success(self):
        db = FakeMotelDb([_room("1")], unreadable=True)
        res = await ch._check_appwrite_availability(db, FRI, SUN)
        assert res["success"] is False

    async def test_check_availability_reports_unknown(self):
        db = FakeMotelDb([_room("1")], unreadable=True)
        out = await ch.handle_check_availability(
            {"check_in_date": FRI, "check_out_date": SUN, "room_type": "queen"}, db)
        assert out["available"] == "unknown"
        assert out["verified"] is False

    async def test_booking_assigns_no_room_and_saves_nothing(self):
        db = FakeMotelDb([_room("1")], unreadable=True)

        result = await _book(db)

        assert result["success"] is False
        assert result["available"] == "unknown"
        assert "haven't placed the hold" in result["message"]
        assert db.saved == []

    async def test_empty_room_inventory_is_a_failed_read_not_fully_booked(self):
        """get_motel_rooms still returns [] on error; no rooms is never real."""
        db = FakeMotelDb([])
        out = await ch.handle_check_availability(
            {"check_in_date": FRI, "check_out_date": SUN, "room_type": "any"}, db)
        assert out["available"] == "unknown"


class TestGetMotelReservationsContract:
    """The DB layer itself: None for "could not read", [] for "nothing booked"."""

    def _svc(self, make_request):
        from services.db.bookings import BookingsMixin
        from appwrite.query import Query

        class FakeDb(BookingsMixin):
            motel_db_id = "motel_db_test"

        FakeDb.Query = Query
        svc = FakeDb()
        svc._make_request = make_request
        return svc

    async def test_http_error_is_none(self):
        svc = self._svc(AsyncMock(return_value=None))  # _make_request's error value
        assert await svc.get_motel_reservations(FRI, SUN) is None

    async def test_exception_is_none(self):
        svc = self._svc(AsyncMock(side_effect=RuntimeError("boom")))
        assert await svc.get_motel_reservations(FRI, SUN) is None

    async def test_no_rows_is_empty_list(self):
        svc = self._svc(AsyncMock(return_value={"documents": []}))
        assert await svc.get_motel_reservations(FRI, SUN) == []

    async def test_pages_newest_first_past_one_page(self, monkeypatch):
        """Rows past the first page used to be invisible; now they are paged in."""
        page1 = [dict(_res("1", "2020-01-01", "2020-01-02"), **{"$id": "a"}),
                 dict(_res("2", "2020-01-01", "2020-01-02"), **{"$id": "b"})]
        page2 = [dict(_res("3", FRI, SAT), **{"$id": "c"})]
        req = AsyncMock(side_effect=[{"documents": page1}, {"documents": page2}])
        svc = self._svc(req)
        monkeypatch.setattr(type(svc), "_RESERVATION_PAGE_SIZE", 2)

        found = await svc.get_motel_reservations(FRI, SUN)

        assert [r["room_number"] for r in found] == ["3"]
        first_q = [str(q) for q in req.call_args_list[0].kwargs["params"]["queries"]]
        second_q = [str(q) for q in req.call_args_list[1].kwargs["params"]["queries"]]
        assert any("orderDesc" in q and "$createdAt" in q for q in first_q)
        assert any("cursorAfter" in q and '"b"' in q for q in second_q)

    async def test_failure_on_a_later_page_is_none_not_partial(self, monkeypatch):
        page1 = [dict(_res("1", FRI, SAT), **{"$id": "a"})]
        svc = self._svc(AsyncMock(side_effect=[{"documents": page1}, None]))
        monkeypatch.setattr(type(svc), "_RESERVATION_PAGE_SIZE", 1)
        assert await svc.get_motel_reservations(FRI, SUN) is None

    async def test_running_out_of_pages_is_none_not_partial(self, monkeypatch):
        full = {"documents": [dict(_res("1", FRI, SAT), **{"$id": "a"})]}
        svc = self._svc(AsyncMock(return_value=full))
        monkeypatch.setattr(type(svc), "_RESERVATION_PAGE_SIZE", 1)
        monkeypatch.setattr(type(svc), "_RESERVATION_MAX_PAGES", 3)
        assert await svc.get_motel_reservations(FRI, SUN) is None

    async def test_cancelled_rows_free_the_room_case_insensitively(self):
        rows = [dict(_res("1", FRI, SAT), status="Cancelled"), _res("2", FRI, SAT)]
        svc = self._svc(AsyncMock(return_value={"documents": rows}))
        assert [r["room_number"] for r in await svc.get_motel_reservations(FRI, SUN)] == ["2"]


# ---------------------------------------------------------------------------
# 3. Two callers, one room
# ---------------------------------------------------------------------------

class TestTheLastRoomIsSoldOnce:

    async def test_concurrent_bookings_for_the_last_room(self):
        db = FakeMotelDb([_room("1")], save_delay=0.01)

        a, b = await asyncio.gather(_book(db, name="Alice"), _book(db, name="Bob"))

        assert sorted([a["success"], b["success"]]) == [False, True]
        assert [s["room_number"] for s in db.saved] == ["1"]
        loser = a if not a["success"] else b
        assert "no longer available" in loser["message"]

    async def test_concurrent_bookings_of_different_types_both_succeed(self):
        """The lock is per type, so the guard never turns away an unrelated booking."""
        db = FakeMotelDb([_room("1"), _room("5", "twin")], save_delay=0.01)

        a, b = await asyncio.gather(_book(db, room="queen"), _book(db, room="twin"))

        assert a["success"] and b["success"]
        assert sorted(s["room_number"] for s in db.saved) == ["1", "5"]
