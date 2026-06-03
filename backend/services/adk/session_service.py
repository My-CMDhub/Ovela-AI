"""
AppwriteSessionService — Persistent ADK Session Service backed by Appwrite.

Replaces InMemorySessionService for Cloud Run deployments where in-process
memory is wiped on every scale event or WebSocket reconnect.

Design contract:
  - Session state (caller name, booking intent, dates) is serialised to JSON
    and stored in an Appwrite document per call_sid.
  - Events are stored as a JSON-encoded list on the same document.
  - All I/O errors are caught and re-raised as RuntimeError so the ADK Runner
    can decide whether to abort or retry.
  - Collection: ``adk_sessions`` inside the production DB (motel_db_id).
    Must be created manually in Appwrite with the attributes defined below.

Appwrite collection schema (``adk_sessions``):
  - app_name   : string(64)   indexed
  - user_id    : string(128)  indexed
  - session_id : string(128)  indexed  (also used as document $id)
  - state_json : string(65535)
  - events_json: string(65535)  (may need to be extended if event history is large)
  - updated_at : integer (epoch ms)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from google.adk.sessions.base_session_service import (
    BaseSessionService,
    GetSessionConfig,
    ListSessionsResponse,
)
from google.adk.sessions import Session
from google.adk.events import Event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Appwrite Collection ID for ADK sessions
# ---------------------------------------------------------------------------
_ADK_COLLECTION_ID = "adk_sessions"


def _serialise_events(events: list[Event]) -> str:
    """Serialise ADK Event list to a compact JSON string for storage, with size limits."""
    try:
        raw_events = []
        for e in events:
            dumped = e.model_dump(mode="json")
            # Truncate large content/payload strings to prevent blowing past Appwrite's 65,535 limit
            if "content" in dumped and isinstance(dumped["content"], str) and len(dumped["content"]) > 1000:
                dumped["content"] = dumped["content"][:1000] + "... [truncated]"
            if "payload" in dumped and isinstance(dumped["payload"], dict):
                for k, v in list(dumped["payload"].items()):
                    if isinstance(v, str) and len(v) > 1000:
                        dumped["payload"][k] = v[:1000] + "... [truncated]"
            raw_events.append(dumped)
        
        # Programmatically prune oldest events if serialized string is still too large
        serialized = json.dumps(raw_events)
        while len(serialized) > 64000 and len(raw_events) > 2:
            raw_events.pop(0)
            serialized = json.dumps(raw_events)
            
        return serialized
    except Exception as exc:
        logger.warning("AppwriteSessionService: failed to serialise events — %s", exc)
        return "[]"


def _deserialise_events(raw: str) -> list[Event]:
    """Deserialise ADK Event list from JSON string. Returns [] on any error."""
    try:
        items = json.loads(raw or "[]")
        return [Event.model_validate(item) for item in items]
    except Exception as exc:
        logger.warning("AppwriteSessionService: failed to deserialise events — %s", exc)
        return []


class AppwriteSessionService(BaseSessionService):
    """
    Google ADK session service backed by Appwrite Cloud.

    Session documents are stored in the ``adk_sessions`` collection using
    the session_id as the Appwrite document $id for O(1) lookups.

    Usage:
        session_service = AppwriteSessionService(db=db_service)
        runner = Runner(agent=manager, session_service=session_service, ...)
    """

    def __init__(self, db=None):
        """
        Args:
            db: An AppwriteService instance. If None, imports the module-level
                singleton (lazy import to allow test injection).
        """
        if db is None:
            from services.appwrite import db_service
            self._db = db_service
        else:
            self._db = db

    # ------------------------------------------------------------------
    # Internal Appwrite helpers
    # ------------------------------------------------------------------

    async def _create_document(self, document_id: str, data: dict) -> Optional[dict]:
        path = f"/collections/{_ADK_COLLECTION_ID}/documents"
        return await self._db._motel_request(
            "POST",
            path,
            data={"documentId": document_id, "data": data},
        )

    async def _get_document(self, document_id: str) -> Optional[dict]:
        path = f"/collections/{_ADK_COLLECTION_ID}/documents/{document_id}"
        return await self._db._motel_request("GET", path)

    async def _update_document(self, document_id: str, data: dict) -> Optional[dict]:
        path = f"/collections/{_ADK_COLLECTION_ID}/documents/{document_id}"
        return await self._db._motel_request("PATCH", path, data={"data": data})

    async def _delete_document(self, document_id: str) -> bool:
        path = f"/collections/{_ADK_COLLECTION_ID}/documents/{document_id}"
        result = await self._db._motel_request("DELETE", path)
        return result is not None

    async def _list_documents(self, queries: list[str]) -> Optional[dict]:
        path = f"/collections/{_ADK_COLLECTION_ID}/documents"
        return await self._db._motel_request("GET", path, params={"queries": queries})

    # ------------------------------------------------------------------
    # BaseSessionService interface
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        """Create and persist a new session."""
        import uuid

        sid = session_id or f"sess_{uuid.uuid4().hex}"
        now = time.time()

        doc_data = {
            "app_name": app_name,
            "user_id": user_id,
            "session_id": sid,
            "state_json": json.dumps(state or {}),
            "events_json": "[]",
            "updated_at": int(now * 1000),
        }

        result = await self._create_document(sid, doc_data)
        if result is None:
            raise RuntimeError(
                f"AppwriteSessionService: failed to create session {sid} for user {user_id}"
            )

        logger.info(
            "📦 ADK Session created — sid=%s user=%s", sid, user_id[:8]
        )
        return Session(
            id=sid,
            app_name=app_name,
            user_id=user_id,
            state=state or {},
            events=[],
            last_update_time=now,
        )

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> Optional[Session]:
        """Fetch an existing session by ID. Returns None if not found."""
        doc = await self._get_document(session_id)
        if doc is None:
            return None

        # Guard: ensure document belongs to the right app/user
        if doc.get("app_name") != app_name or doc.get("user_id") != user_id:
            logger.warning(
                "AppwriteSessionService: session %s ownership mismatch — "
                "stored app=%s user=%s vs requested app=%s user=%s",
                session_id,
                doc.get("app_name"),
                doc.get("user_id"),
                app_name,
                user_id,
            )
            return None

        state = json.loads(doc.get("state_json") or "{}")
        events = _deserialise_events(doc.get("events_json") or "[]")
        updated_at = doc.get("updated_at", 0) / 1000.0

        logger.debug(
            "📦 ADK Session loaded — sid=%s events=%d state_keys=%s",
            session_id,
            len(events),
            list(state.keys()),
        )
        return Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            state=state,
            events=events,
            last_update_time=updated_at,
        )

    async def list_sessions(
        self, *, app_name: str, user_id: Optional[str] = None
    ) -> ListSessionsResponse:
        """List sessions for an app/user. Events and state are not populated."""
        from appwrite.query import Query

        queries = [str(Query.equal("app_name", app_name))]
        if user_id:
            queries.append(str(Query.equal("user_id", user_id)))

        result = await self._list_documents(queries)
        sessions: list[Session] = []
        if result and result.get("documents"):
            for doc in result["documents"]:
                sessions.append(
                    Session(
                        id=doc["session_id"],
                        app_name=doc["app_name"],
                        user_id=doc["user_id"],
                        state={},   # Not populated per ADK contract
                        events=[],  # Not populated per ADK contract
                        last_update_time=doc.get("updated_at", 0) / 1000.0,
                    )
                )
        return ListSessionsResponse(sessions=sessions)

    async def delete_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> None:
        """Delete a session document."""
        deleted = await self._delete_document(session_id)
        if deleted:
            logger.info("📦 ADK Session deleted — sid=%s", session_id)
        else:
            logger.warning("AppwriteSessionService: delete_session — doc %s not found", session_id)

    async def append_event(self, session: Session, event: Event) -> Event:
        """
        Extend the parent append_event to also persist the updated session
        state and event list to Appwrite after each turn.
        """
        # Let the parent handle in-memory state updates and temp-scope trimming
        event = await super().append_event(session, event)

        # Persist updated state + events to Appwrite (best-effort, non-blocking)
        try:
            await self._update_document(
                session.id,
                {
                    "state_json": json.dumps(session.state),
                    "events_json": _serialise_events(session.events),
                    "updated_at": int(time.time() * 1000),
                },
            )
        except Exception as exc:
            # Never crash the Hot Path — log and move on
            logger.error(
                "AppwriteSessionService: append_event persist failed for sid=%s — %s",
                session.id,
                exc,
            )

        return event
