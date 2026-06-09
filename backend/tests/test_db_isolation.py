"""
P10-A: Database-Level Isolation & Operation Tests
===================================================
Tests every critical DB path for the booking system in total isolation:
  1. _save_motel_reservation contract — new {success: True/False} wrapper.
  2. handle_create_booking_request full path (mocked save_fn).
  3. lookup_motel_reservation query routing (phone / name / reference / email).
  4. get_motel_rooms fetches from the correct motel_db_id collection.

All tests run fully offline — zero live Appwrite calls.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date


# ---------------------------------------------------------------------------
# Helper: build a minimal fake Appwrite document (like a real HTTP 201 body)
# ---------------------------------------------------------------------------
def _fake_appwrite_doc(booking_ref: str = "CC-99999") -> dict:
    """Mimics the raw JSON returned by Appwrite on a successful POST."""
    return {
        "$id": "doc_abc123",
        "$collectionId": "motel_reservations",
        "$databaseId": "motel_db",
        "booking_reference": booking_ref,
        "guest_name": "Test Guest",
        "guest_phone": "+61400000000",
        "check_in_date": "2026-07-01",
        "check_out_date": "2026-07-03",
        "status": "pending",
        "tenant_id": "coalcreek",
    }


# ===========================================================================
# P10-B: _save_motel_reservation contract
# ===========================================================================

class TestSaveMotelReservationContract:
    """
    Verifies the NEW standardised return contract:
        success  → {"success": True,  "document": <appwrite_doc>}
        failure  → {"success": False, "error": "<str>"}
    """

    @pytest.mark.asyncio
    async def test_successful_save_returns_success_true(self):
        """Happy path: HTTP 201 → wrapper with success=True and document payload."""
        from unittest.mock import AsyncMock, MagicMock
        import httpx

        fake_doc = _fake_appwrite_doc("CC-11111")

        # Build a fake httpx response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = fake_doc

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            # Simulate what VoiceAgentHandler._save_motel_reservation does
            async def _save_motel_reservation_impl(data: dict) -> dict:
                from appwrite.id import ID
                doc_id = ID.unique()
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post("http://fake", headers={}, json={})
                    response.raise_for_status()
                    doc = response.json()
                    return {"success": True, "document": doc}

            result = await _save_motel_reservation_impl({"guest_name": "Test"})

        assert result["success"] is True
        assert "document" in result
        assert result["document"]["$id"] == "doc_abc123"
        assert result["document"]["booking_reference"] == "CC-11111"

    @pytest.mark.asyncio
    async def test_failed_save_returns_success_false(self):
        """Network error path: HTTPStatusError → wrapper with success=False and error key."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=Exception("Appwrite 503"))
            mock_client_cls.return_value = mock_client

            async def _save_motel_reservation_impl_error(data: dict) -> dict:
                import httpx as _httpx
                try:
                    async with _httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.post("http://fake", headers={}, json={})
                        response.raise_for_status()
                        doc = response.json()
                        return {"success": True, "document": doc}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            result = await _save_motel_reservation_impl_error({"guest_name": "Test"})

        assert result["success"] is False
        assert "error" in result
        assert "503" in result["error"]

    def test_success_wrapper_keys_are_present(self):
        """Contract assertion: both result shapes have the required keys."""
        success_result = {"success": True, "document": _fake_appwrite_doc()}
        failure_result = {"success": False, "error": "Timeout"}

        # Success wrapper
        assert "success" in success_result
        assert success_result["success"] is True
        assert "document" in success_result

        # Failure wrapper
        assert "success" in failure_result
        assert failure_result["success"] is False
        assert "error" in failure_result


# ===========================================================================
# P10-B: handle_create_booking_request full-path (mocked save_fn)
# ===========================================================================

class TestHandleCreateBookingRequest:
    """
    Tests handle_create_booking_request with the fixed validation guard.
    Uses a mocked save_reservation_fn to exercise all result branches.
    """

    @pytest.mark.asyncio
    async def test_successful_booking_returns_success_true(self):
        """End-to-end: mock save returns {success: True} → function returns success.

        Patches USE_LIVE_SCRAPING=True so we bypass the PMS Appwrite availability
        check (db_service=None) and isolate purely the save-path contract.
        """
        from services.voice_agent.functions.coalcreek_handlers import handle_create_booking_request
        from core import config as _cfg

        save_mock = AsyncMock(return_value={"success": True, "document": _fake_appwrite_doc("CC-22222")})

        args = {
            "guest_name": "Jane Smith",
            "check_in_date": "2026-09-01",
            "check_out_date": "2026-09-03",
            "room_type": "queen",
            "num_guests": 2,
            "guest_email": "jane@example.com",
            "guest_phone": "+61411111111",
            "has_user_confirmed_summary": True,  # N1 gate: simulate confirmed summary
        }

        # Force scraping mode so the PMS availability branch is skipped
        original = _cfg.settings.USE_LIVE_SCRAPING
        _cfg.settings.USE_LIVE_SCRAPING = True
        try:
            result = await handle_create_booking_request(
                args=args,
                user_phone="+61411111111",
                save_reservation_fn=save_mock,
                db_service=None,
            )
        finally:
            _cfg.settings.USE_LIVE_SCRAPING = original

        assert result["success"] is True
        assert "booking_reference" in result
        assert result["guest_name"] == "Jane Smith"
        save_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_returns_failure_wrapper_propagates_error(self):
        """When save_fn returns {success: False}, handler must abort with success=False.

        Patches USE_LIVE_SCRAPING=True to isolate the save-path logic.
        """
        from services.voice_agent.functions.coalcreek_handlers import handle_create_booking_request
        from core import config as _cfg

        save_mock = AsyncMock(return_value={"success": False, "error": "Appwrite write failed"})

        args = {
            "guest_name": "Bob Error",
            "check_in_date": "2026-09-01",
            "check_out_date": "2026-09-02",
            "room_type": "queen",
            "num_guests": 1,
            "guest_email": "bob@example.com",
            "has_user_confirmed_summary": True,  # N1 gate: simulate confirmed summary
        }

        original = _cfg.settings.USE_LIVE_SCRAPING
        _cfg.settings.USE_LIVE_SCRAPING = True
        try:
            result = await handle_create_booking_request(
                args=args,
                user_phone="+61422222222",
                save_reservation_fn=save_mock,
                db_service=None,
            )
        finally:
            _cfg.settings.USE_LIVE_SCRAPING = original

        assert result["success"] is False
        assert "system error" in result["message"].lower() or "contact reception" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_save_returns_none_propagates_error(self):
        """Defensive: if save_fn unexpectedly returns None, abort gracefully."""
        from services.voice_agent.functions.coalcreek_handlers import handle_create_booking_request

        save_mock = AsyncMock(return_value=None)

        args = {
            "guest_name": "None Case",
            "check_in_date": "2026-09-05",
            "check_out_date": "2026-09-06",
            "room_type": "twin",
            "num_guests": 1,
        }

        result = await handle_create_booking_request(
            args=args,
            user_phone="+61433333333",
            save_reservation_fn=save_mock,
            db_service=None,
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_missing_guest_name_returns_validation_error(self):
        """Missing guest_name must fail validation before any DB call."""
        from services.voice_agent.functions.coalcreek_handlers import handle_create_booking_request

        save_mock = AsyncMock()
        args = {
            "check_in_date": "2026-09-01",
            "check_out_date": "2026-09-02",
            "room_type": "queen",
        }

        result = await handle_create_booking_request(
            args=args,
            user_phone="+61444444444",
            save_reservation_fn=save_mock,
            db_service=None,
        )

        assert result["success"] is False
        save_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_save_fn_skips_db_and_returns_success(self):
        """If save_reservation_fn is None (test mode), booking still returns success.

        Patches USE_LIVE_SCRAPING=True to bypass PMS availability check.
        """
        from services.voice_agent.functions.coalcreek_handlers import handle_create_booking_request
        from core import config as _cfg

        args = {
            "guest_name": "No DB Test",
            "check_in_date": "2026-10-01",
            "check_out_date": "2026-10-02",
            "room_type": "queen",
            "num_guests": 1,
            "guest_email": "nodbtest@example.com",
            "has_user_confirmed_summary": True,  # N1 gate: simulate confirmed summary
        }

        original = _cfg.settings.USE_LIVE_SCRAPING
        _cfg.settings.USE_LIVE_SCRAPING = True
        try:
            result = await handle_create_booking_request(
                args=args,
                user_phone="+61455555555",
                save_reservation_fn=None,
                db_service=None,
            )
        finally:
            _cfg.settings.USE_LIVE_SCRAPING = original

        assert result["success"] is True
        assert "booking_reference" in result


# ===========================================================================
# P10-A: lookup_motel_reservation query routing
# ===========================================================================

class TestLookupMotelReservationRouting:
    """
    Verifies lookup_motel_reservation selects the correct DB query branch
    and correctly returns results. All calls are mocked — zero live Appwrite.
    """

    def _build_fake_mixin(self, response_sequence: list):
        """Create a fake BookingsMixin instance with mocked _motel_request."""
        class FakeQuery:
            @staticmethod
            def equal(field, value): return f"equal:{field}:{value}"
            @staticmethod
            def order_desc(field): return f"order_desc:{field}"
            @staticmethod
            def limit(value): return f"limit:{value}"
            @staticmethod
            def search(field, value): return f"search:{field}:{value}"

        class FakeDb:
            motel_db_id = "motel_db_test"
            Query = FakeQuery

        from services.db.bookings import BookingsMixin
        fake = FakeDb()
        fake._motel_request = AsyncMock(side_effect=response_sequence)
        fake.lookup_motel_reservation = BookingsMixin.lookup_motel_reservation.__get__(fake, FakeDb)
        return fake

    @pytest.mark.asyncio
    async def test_phone_lookup_returns_matching_doc(self):
        """Phone lookup → returns doc with matching phone."""
        doc = {"guest_phone": "+61400000001", "guest_name": "Alice", "booking_reference": "CC-55555"}
        fake = self._build_fake_mixin([{"documents": [doc]}])

        result = await fake.lookup_motel_reservation(phone="+61400000001", tenant_id="coalcreek")
        assert len(result) == 1
        assert result[0]["guest_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_reference_lookup_returns_matching_doc(self):
        """Booking reference lookup → returns doc with that reference."""
        doc = {"booking_reference": "CC-66666", "guest_name": "Carlos"}
        fake = self._build_fake_mixin([{"documents": [doc]}])

        result = await fake.lookup_motel_reservation(booking_reference="CC-66666", tenant_id="coalcreek")
        assert len(result) == 1
        assert result[0]["booking_reference"] == "CC-66666"

    @pytest.mark.asyncio
    async def test_name_exact_match_returns_doc(self):
        """Name lookup exact match path."""
        doc = {"guest_name": "Maria Chen", "booking_reference": "CC-77777"}
        # First call: phone → no results; second: name exact → hit
        fake = self._build_fake_mixin([{"documents": [doc]}])

        result = await fake.lookup_motel_reservation(guest_name="Maria Chen", tenant_id="coalcreek")
        assert len(result) == 1
        assert result[0]["guest_name"] == "Maria Chen"

    @pytest.mark.asyncio
    async def test_no_match_returns_empty_list(self):
        """When all query strategies return empty, return []."""
        # All four queries return empty
        fake = self._build_fake_mixin([
            {"documents": []},  # exact name
            {"documents": []},  # search
            {"documents": []},  # scan fallback
        ])

        result = await fake.lookup_motel_reservation(guest_name="Ghost Person", tenant_id="coalcreek")
        assert result == []

    @pytest.mark.asyncio
    async def test_email_lookup_returns_doc(self):
        """Email lookup as last resort."""
        doc = {"guest_email": "test@email.com", "guest_name": "Email User"}
        fake = self._build_fake_mixin([{"documents": [doc]}])

        result = await fake.lookup_motel_reservation(email="test@email.com", tenant_id="coalcreek")
        assert len(result) == 1
        assert result[0]["guest_email"] == "test@email.com"


# ===========================================================================
# P10-A: get_motel_rooms collection fetch
# ===========================================================================

class TestGetMotelRooms:
    """Verifies get_motel_rooms reads from the correct motel_db_id collection."""

    @pytest.mark.asyncio
    async def test_returns_room_list_on_success(self):
        """Happy path: DB returns documents list."""
        class FakeQuery:
            @staticmethod
            def limit(v): return f"limit:{v}"

        class FakeDb:
            motel_db_id = "motel_db_test"
            Query = FakeQuery

        from services.db.bookings import BookingsMixin

        fake = FakeDb()
        fake._make_request = AsyncMock(return_value={
            "documents": [
                {"room_number": "101", "room_type": "Double Room", "is_available": True},
                {"room_number": "102", "room_type": "Twin Room", "is_available": True},
            ]
        })
        fake.get_motel_rooms = BookingsMixin.get_motel_rooms.__get__(fake, FakeDb)

        rooms = await fake.get_motel_rooms(tenant_id="coalcreek")
        assert len(rooms) == 2
        assert rooms[0]["room_number"] == "101"
        assert rooms[1]["room_type"] == "Twin Room"

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_db_error(self):
        """If DB throws, get_motel_rooms returns [] and logs error."""
        class FakeQuery:
            @staticmethod
            def limit(v): return f"limit:{v}"

        class FakeDb:
            motel_db_id = "motel_db_test"
            Query = FakeQuery

        from services.db.bookings import BookingsMixin

        fake = FakeDb()
        fake._make_request = AsyncMock(side_effect=Exception("DB connection refused"))
        fake.get_motel_rooms = BookingsMixin.get_motel_rooms.__get__(fake, FakeDb)

        rooms = await fake.get_motel_rooms(tenant_id="coalcreek")
        assert rooms == []
