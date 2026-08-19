"""
Regression tests for the per-call reservation lookup memo.

Live trace CA591f56d4f5055bd64cb598b2de7a58cd: `lookup_booking` fired 8 times
in one 204s call, each firing 1-3 sequential Appwrite round trips (~250ms
each), for turn totals of 1.1-1.6s against a 800ms TTFA budget. The caller's
booking cannot change between two turns of the same call unless we changed it,
so every repeat was pure latency.
"""

import asyncio

import pytest

from services.voice_agent.functions.coalcreek_handlers import _CachedReservationLookup


class FakeDB:
    """Counts round trips. Everything else must pass through untouched."""

    db_id = "sentinel-db"

    def __init__(self, delay: float = 0.0, docs=None):
        self.calls: list[dict] = []
        self.delay = delay
        self.docs = docs if docs is not None else [{"guest_name": "Test Guest"}]

    async def lookup_motel_reservation(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.docs

    async def save_motel_reservation(self, data, tenant_id="coalcreek"):
        return {"$id": "saved"}


async def test_identical_lookups_hit_the_database_once():
    db = FakeDB()
    cached = _CachedReservationLookup(db)

    for _ in range(8):
        docs = await cached.lookup_motel_reservation(phone="+61400000000", tenant_id="coalcreek")
        assert docs == [{"guest_name": "Test Guest"}]

    assert len(db.calls) == 1, f"expected 1 round trip, made {len(db.calls)}"


async def test_different_arguments_are_cached_separately():
    db = FakeDB()
    cached = _CachedReservationLookup(db)

    await cached.lookup_motel_reservation(phone="+61400000000", tenant_id="coalcreek")
    await cached.lookup_motel_reservation(guest_name="Test Guest", tenant_id="coalcreek")
    await cached.lookup_motel_reservation(phone="+61400000000", tenant_id="coalcreek")

    assert len(db.calls) == 2


async def test_concurrent_callers_join_one_in_flight_request():
    """Prefetch and the first tool call race. The second must not re-query."""
    db = FakeDB(delay=0.05)
    cached = _CachedReservationLookup(db)

    await asyncio.gather(*[
        cached.lookup_motel_reservation(phone="+61400000000", tenant_id="coalcreek")
        for _ in range(4)
    ])

    assert len(db.calls) == 1


async def test_invalidate_forces_a_refetch_after_a_write():
    db = FakeDB()
    cached = _CachedReservationLookup(db)

    await cached.lookup_motel_reservation(phone="+61400000000", tenant_id="coalcreek")
    cached.invalidate()
    await cached.lookup_motel_reservation(phone="+61400000000", tenant_id="coalcreek")

    assert len(db.calls) == 2


async def test_a_failed_lookup_is_not_cached():
    """A transient Appwrite error must not poison the rest of the call."""

    class FlakyDB(FakeDB):
        async def lookup_motel_reservation(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise RuntimeError("appwrite timeout")
            return self.docs

    db = FlakyDB()
    cached = _CachedReservationLookup(db)

    with pytest.raises(RuntimeError):
        await cached.lookup_motel_reservation(phone="+61400000000", tenant_id="coalcreek")

    docs = await cached.lookup_motel_reservation(phone="+61400000000", tenant_id="coalcreek")
    assert docs == [{"guest_name": "Test Guest"}]
    assert len(db.calls) == 2


async def test_everything_else_delegates_to_the_real_service():
    db = FakeDB()
    cached = _CachedReservationLookup(db)

    assert cached.db_id == "sentinel-db"
    assert await cached.save_motel_reservation({"a": 1}) == {"$id": "saved"}
