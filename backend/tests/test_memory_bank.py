"""
Tests for CallerMemoryBank — persistent caller recognition across sessions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.anyio
async def test_caller_recognition_returns_profile_for_known_caller():
    """Known caller: profile returned with name and room preference."""
    db_mock = AsyncMock()
    db_mock.get_caller_profile.return_value = {
        "name": "Jane",
        "email": "jane@example.com",
        "room_preference": "queen",
        "last_visit": "2026-01-10",
    }

    from services.voice_agent.memory import CallerMemoryBank
    bank = CallerMemoryBank(db=db_mock)
    profile = await bank.get_profile("+61400111222")

    assert profile["name"] == "Jane"
    assert profile["room_preference"] == "queen"
    db_mock.get_caller_profile.assert_awaited_once_with("+61400111222")


@pytest.mark.anyio
async def test_caller_recognition_returns_empty_for_unknown_caller():
    """Unknown caller: returns safe empty profile, does not raise."""
    db_mock = AsyncMock()
    db_mock.get_caller_profile.return_value = None

    from services.voice_agent.memory import CallerMemoryBank
    bank = CallerMemoryBank(db=db_mock)
    profile = await bank.get_profile("+61400000000")

    assert profile["name"] is None
    assert profile["email"] is None
    assert profile["room_preference"] is None


@pytest.mark.anyio
async def test_caller_recognition_returns_empty_on_db_error():
    """DB failure: silently returns safe empty profile rather than raising."""
    db_mock = AsyncMock()
    db_mock.get_caller_profile.side_effect = Exception("Appwrite timeout")

    from services.voice_agent.memory import CallerMemoryBank
    bank = CallerMemoryBank(db=db_mock)
    profile = await bank.get_profile("+61400111222")

    assert profile["name"] is None
    assert profile["room_preference"] is None


@pytest.mark.anyio
async def test_save_profile_calls_db_correctly():
    """save_profile correctly delegates to db with phone and data."""
    db_mock = AsyncMock()
    db_mock.save_caller_profile.return_value = None

    from services.voice_agent.memory import CallerMemoryBank
    bank = CallerMemoryBank(db=db_mock)
    await bank.save_profile("+61400111222", {"name": "Jane", "room_preference": "queen"})

    db_mock.save_caller_profile.assert_awaited_once_with(
        "+61400111222", {"name": "Jane", "room_preference": "queen"}
    )


@pytest.mark.anyio
async def test_save_profile_swallows_db_error():
    """DB failure on save: does not propagate exception — hot path must stay safe."""
    db_mock = AsyncMock()
    db_mock.save_caller_profile.side_effect = Exception("Appwrite write failed")

    from services.voice_agent.memory import CallerMemoryBank
    bank = CallerMemoryBank(db=db_mock)

    # Must not raise
    await bank.save_profile("+61400111222", {"name": "Jane"})
