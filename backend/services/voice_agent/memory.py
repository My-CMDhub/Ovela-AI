"""
CallerMemoryBank — Persistent caller profile recognition across call sessions.

Reads and writes caller profiles to Appwrite by phone number so that returning
guests are recognised immediately and conversational amnesia is eliminated.

Hot-path contract:
  - get_profile() NEVER raises — silently returns an empty profile on any error.
  - save_profile() NEVER raises — silently logs and swallows all DB errors.

This ensures a DB outage cannot crash the voice agent's WebSocket handler.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Safe empty profile returned when caller is unknown or DB is unavailable.
_EMPTY_PROFILE: dict[str, Any] = {
    "name": None,
    "email": None,
    "room_preference": None,
    "last_visit": None,
    "notes": None,
}


class CallerMemoryBank:
    """
    Persistent caller profile store backed by Appwrite.

    Usage:
        bank = CallerMemoryBank()                 # uses live db_service
        bank = CallerMemoryBank(db=mock_db)       # inject mock in tests

    Methods:
        get_profile(phone)         -> dict   # always safe, never raises
        save_profile(phone, data)  -> None   # fire-and-forget, never raises
    """

    def __init__(self, db=None):
        if db is None:
            # Lazy import so tests can inject a mock without importing Appwrite.
            from services.appwrite import db_service
            self.db = db_service
        else:
            self.db = db

    async def get_profile(self, phone: str) -> dict[str, Any]:
        """
        Fetch caller profile by phone number.

        Returns the stored profile dict if found, or _EMPTY_PROFILE if the
        caller is new or the DB is unavailable. Never raises.

        Args:
            phone: E.164-format caller phone (e.g. '+61400111222').

        Returns:
            dict with keys: name, email, room_preference, last_visit, notes.
        """
        try:
            profile = await self.db.get_caller_profile(phone)
            if profile:
                logger.info(
                    "🧠 CallerMemoryBank: Returning caller recognised — %s",
                    phone[:4] + "****",
                )
                return profile
            logger.debug("🧠 CallerMemoryBank: New caller — no profile for %s", phone[:4] + "****")
        except Exception as exc:
            logger.error("🧠 CallerMemoryBank: get_profile failed for %s — %s", phone[:4] + "****", exc)
        return dict(_EMPTY_PROFILE)

    async def save_profile(self, phone: str, data: dict) -> None:
        """
        Persist or update caller profile in Appwrite.

        Fire-and-forget: errors are logged but never re-raised.

        Args:
            phone: E.164-format caller phone.
            data:  Dict of fields to write (name, email, room_preference, etc.).
        """
        try:
            await self.db.save_caller_profile(phone, data)
            logger.info(
                "🧠 CallerMemoryBank: Profile saved for %s — keys: %s",
                phone[:4] + "****",
                list(data.keys()),
            )
        except Exception as exc:
            logger.error(
                "🧠 CallerMemoryBank: save_profile failed for %s — %s",
                phone[:4] + "****",
                exc,
            )
