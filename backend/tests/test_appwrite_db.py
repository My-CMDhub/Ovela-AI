import pytest
from unittest.mock import AsyncMock

from services.appwrite import db_service

def test_db_service_mixin_integrity():
    # Verify that the AppwriteService successfully inherits and exposes all essential methods
    assert hasattr(db_service, "get_bookings")
    assert hasattr(db_service, "create_booking")
    assert hasattr(db_service, "get_tenant_settings")
    assert hasattr(db_service, "get_tenant_config")
    
    # Assert base DB ID is set
    assert db_service.db_id is not None
    assert db_service.motel_db_id is not None


@pytest.mark.asyncio
async def test_lookup_motel_reservation_falls_back_to_python_name_filter_without_fulltext_index():
    class FakeQuery:
        @staticmethod
        def equal(field, value):
            return f"equal:{field}:{value}"

        @staticmethod
        def order_desc(field):
            return f"order_desc:{field}"

        @staticmethod
        def limit(value):
            return f"limit:{value}"

        @staticmethod
        def search(field, value):
            return f"search:{field}:{value}"

    class FakeDb:
        motel_db_id = "motel_db"
        Query = FakeQuery

    from services.db.bookings import BookingsMixin

    fake_db = FakeDb()
    # A name-only lookup goes straight to the roster: an exact index hit is
    # exactly what returns the wrong guest for a homophone name.
    fake_db._motel_request = AsyncMock(side_effect=[
        {"documents": [
            {"guest_name": "Emma Clark", "booking_reference": "CC-10001"},
            {"guest_name": "Tom Harris", "booking_reference": "CC-10002"},
        ]},
    ])
    for method in ("lookup_motel_reservation", "_recent_reservations"):
        setattr(fake_db, method, getattr(BookingsMixin, method).__get__(fake_db, FakeDb))

    docs = await fake_db.lookup_motel_reservation(guest_name="emma  CLARK", tenant_id="coalcreek")

    assert len(docs) == 1
    assert docs[0]["guest_name"] == "Emma Clark"


@pytest.mark.asyncio
async def test_lookup_motel_reservation_resolves_a_misheard_name_through_the_db_layer():
    """The fuzzy rung, reached the way a live call reaches it."""
    class FakeQuery:
        equal = staticmethod(lambda f, v: f"equal:{f}:{v}")
        order_desc = staticmethod(lambda f: f"order_desc:{f}")
        limit = staticmethod(lambda v: f"limit:{v}")

    class FakeDb:
        motel_db_id = "motel_db"
        Query = FakeQuery

    from services.db.bookings import BookingsMixin

    fake_db = FakeDb()
    fake_db._motel_request = AsyncMock(side_effect=[
        {"documents": [
            {"guest_name": "Dhruv Patel", "booking_reference": "CC-76818"},
            {"guest_name": "Priya Patel", "booking_reference": "CC-76819"},
        ]},
    ])
    for method in ("lookup_motel_reservation", "_recent_reservations"):
        setattr(fake_db, method, getattr(BookingsMixin, method).__get__(fake_db, FakeDb))

    docs = await fake_db.lookup_motel_reservation(guest_name="Bhruv Patel", tenant_id="coalcreek")

    assert [d["booking_reference"] for d in docs] == ["CC-76818"]
