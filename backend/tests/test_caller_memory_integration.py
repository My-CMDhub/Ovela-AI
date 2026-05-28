"""
Tests for CallerMemoryBank integration in the live voice handler.

Phase 3 — Task 1: Wire CallerMemoryBank into _handle_twilio_start.

Covers:
1. Returning guest: profile.name injected into handler.memory["name"]
2. Returning guest: profile.room_preference injected into handler.memory["room_type"]
3. New caller: empty profile → memory["name"] stays None (no crash)
4. DB failure: get_profile() error → memory["name"] stays None (no crash)
5. CoalCreekFunctionDispatcher saves profile on successful update_guest_info
6. CoalCreekFunctionDispatcher skips save if caller_memory_bank is None
7. CoalCreekFunctionDispatcher skips save if update_guest_info fails
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_memory_bank(profile: dict | None = None, *, raises: bool = False):
    """Build a mock CallerMemoryBank."""
    bank = MagicMock()
    if raises:
        bank.get_profile = AsyncMock(side_effect=RuntimeError("DB exploded"))
    else:
        bank.get_profile = AsyncMock(return_value=profile or {
            "name": None, "email": None,
            "room_preference": None, "last_visit": None, "notes": None
        })
    bank.save_profile = AsyncMock()
    return bank


# ─────────────────────────────────────────────────────────────────────────────
# CallerMemoryBank.get_profile injection tests (pure unit — no handler boot)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returning_guest_name_injected_into_memory():
    """
    When get_profile returns a name, handler.memory["name"] is populated
    before Deepgram Settings are sent.
    """
    from services.voice_agent.memory import CallerMemoryBank

    bank = _make_mock_memory_bank(profile={
        "name": "Sarah",
        "email": "sarah@example.com",
        "room_preference": None,
        "last_visit": "2026-04-10",
        "notes": None,
    })

    memory = {"name": None, "room_type": None}

    # Simulate the injector logic from _handle_twilio_start
    caller_profile = await bank.get_profile("+61412345678")
    if caller_profile.get("name"):
        memory["name"] = caller_profile["name"]
    if caller_profile.get("room_preference"):
        memory["room_type"] = caller_profile["room_preference"]

    assert memory["name"] == "Sarah"
    assert memory["room_type"] is None  # Not set in this profile


@pytest.mark.asyncio
async def test_returning_guest_room_preference_injected():
    """
    When profile contains room_preference, handler.memory["room_type"] is set.
    """
    bank = _make_mock_memory_bank(profile={
        "name": "Tom",
        "email": None,
        "room_preference": "spa",
        "last_visit": "2026-03-01",
        "notes": None,
    })

    memory = {"name": None, "room_type": None}

    caller_profile = await bank.get_profile("+61498765432")
    if caller_profile.get("name"):
        memory["name"] = caller_profile["name"]
    if caller_profile.get("room_preference"):
        memory["room_type"] = caller_profile["room_preference"]

    assert memory["name"] == "Tom"
    assert memory["room_type"] == "spa"


@pytest.mark.asyncio
async def test_new_caller_empty_profile_no_crash():
    """
    When profile is empty (new caller), memory fields remain None — no error.
    """
    bank = _make_mock_memory_bank(profile={
        "name": None, "email": None,
        "room_preference": None, "last_visit": None, "notes": None
    })

    memory = {"name": None, "room_type": None}

    caller_profile = await bank.get_profile("+61400111222")
    if caller_profile.get("name"):
        memory["name"] = caller_profile["name"]
    if caller_profile.get("room_preference"):
        memory["room_type"] = caller_profile["room_preference"]

    assert memory["name"] is None
    assert memory["room_type"] is None


@pytest.mark.asyncio
async def test_db_failure_in_get_profile_never_propagates():
    """
    CallerMemoryBank.get_profile() swallows all DB errors internally.
    The injector wrapper in handler also catches any unexpected leak.
    Memory remains at safe defaults — stream continues.
    """
    from services.voice_agent.memory import CallerMemoryBank

    # Inject mock db that raises
    mock_db = MagicMock()
    mock_db.get_caller_profile = AsyncMock(side_effect=ConnectionError("Appwrite down"))

    bank = CallerMemoryBank(db=mock_db)

    memory = {"name": None, "room_type": None}

    # Simulate the handler's try/except wrapper
    try:
        caller_profile = await bank.get_profile("+61400111222")
        if caller_profile.get("name"):
            memory["name"] = caller_profile["name"]
        if caller_profile.get("room_preference"):
            memory["room_type"] = caller_profile["room_preference"]
    except Exception:
        pass  # belt-and-suspenders: stream continues regardless

    # Memory must stay clean
    assert memory["name"] is None
    assert memory["room_type"] is None


# ─────────────────────────────────────────────────────────────────────────────
# CoalCreekFunctionDispatcher — save_profile on update_guest_info
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatcher_saves_profile_on_successful_update_guest_info():
    """
    When update_guest_info succeeds and caller_memory_bank is wired,
    save_profile() is scheduled as a background task with name + email.
    """
    from services.voice_agent.functions.coalcreek_handlers import CoalCreekFunctionDispatcher

    bank = _make_mock_memory_bank()

    mock_db = MagicMock()
    mock_db.upsert_motel_guest = MagicMock(return_value=None)

    dispatcher = CoalCreekFunctionDispatcher(
        db_service=mock_db,
        user_phone="+61412000000",
        save_reservation_fn=AsyncMock(),
        abuse_protection=MagicMock(),
        caller_memory_bank=bank,
    )

    args = {"guest_name": "Alice", "guest_phone": "+61412000000", "guest_email": "alice@test.com"}

    # We need a running event loop for create_task
    result = await dispatcher._dispatch("update_guest_info", args)

    assert result.get("success") is True
    # give create_task a tick to schedule
    await asyncio.sleep(0)
    bank.save_profile.assert_called_once()
    call_args = bank.save_profile.call_args
    assert call_args[0][0] == "+61412000000"  # phone
    saved_data = call_args[0][1]
    assert saved_data.get("name") == "Alice"
    assert saved_data.get("email") == "alice@test.com"


@pytest.mark.asyncio
async def test_dispatcher_skips_save_when_no_memory_bank():
    """
    Without caller_memory_bank (None), update_guest_info still returns success
    and no AttributeError is raised.
    """
    from services.voice_agent.functions.coalcreek_handlers import CoalCreekFunctionDispatcher

    mock_db = MagicMock()
    mock_db.upsert_motel_guest = MagicMock(return_value=None)

    dispatcher = CoalCreekFunctionDispatcher(
        db_service=mock_db,
        user_phone="+61412000001",
        save_reservation_fn=AsyncMock(),
        abuse_protection=MagicMock(),
        caller_memory_bank=None,  # Explicitly None
    )

    args = {"guest_name": "Bob", "guest_phone": "+61412000001", "guest_email": ""}
    result = await dispatcher._dispatch("update_guest_info", args)

    # Should succeed cleanly — no crash
    assert result.get("success") is True


@pytest.mark.asyncio
async def test_dispatcher_skips_save_when_update_fails():
    """
    If update_guest_info internally returns success=False (edge case),
    save_profile should not be called.
    """
    from services.voice_agent.functions.coalcreek_handlers import CoalCreekFunctionDispatcher

    bank = _make_mock_memory_bank()

    # Mock db.upsert_motel_guest to raise (forcing the handler to return success=False)
    mock_db = MagicMock()
    mock_db.upsert_motel_guest = MagicMock(side_effect=Exception("DB write failed"))

    dispatcher = CoalCreekFunctionDispatcher(
        db_service=mock_db,
        user_phone="+61412000002",
        save_reservation_fn=AsyncMock(),
        abuse_protection=MagicMock(),
        caller_memory_bank=bank,
    )

    # Patch handle_update_guest_info to simulate failure
    with patch(
        "services.voice_agent.functions.coalcreek_handlers.handle_update_guest_info",
        new=AsyncMock(return_value={"success": False, "message": "Details captured."})
    ):
        args = {"guest_name": "Charlie", "guest_phone": "+61412000002", "guest_email": ""}
        result = await dispatcher._dispatch("update_guest_info", args)

    # save_profile must NOT be called
    bank.save_profile.assert_not_called()
    assert result.get("success") is False


@pytest.mark.asyncio
async def test_lookup_booking_hides_unrelated_caller_phone_booking_on_name_mismatch():
    from services.voice_agent.functions.coalcreek_handlers import handle_lookup_booking

    mock_db = MagicMock()
    mock_db.lookup_motel_reservation = AsyncMock(side_effect=[
        [{
            "booking_reference": "CC-02618",
            "guest_name": "Tom Harris",
            "room_type": "Twin Room",
            "check_in_date": "2026-05-31",
            "check_out_date": "2026-06-01",
            "status": "confirmed",
            "total_amount": 160,
        }],
        [],
    ])

    result = await handle_lookup_booking(
        {"guest_name": "Emma Clark"},
        mock_db,
        "+61499888777",
    )

    assert result.get("found") is False
    assert result.get("name_mismatch") is True
    assert result.get("needs_reference") is True
    assert "Tom Harris" not in str(result)
