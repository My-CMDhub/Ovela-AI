from .base import AppwriteBase
import logging
import json
import time

logger = logging.getLogger(__name__)

class SessionsMixin(AppwriteBase):
    async def save_hot_path_state(self, call_sid: str, memory_dict: dict) -> None:
        """Save ephemeral hot-path state to adk_sessions to survive Twilio reconnects."""
        try:
            # We prefix the call_sid with 'hp_' to distinguish from ADK sessions
            doc_id = f"hp_{call_sid}"
            now = int(time.time() * 1000)
            data = {
                "app_name": "ovela_hot_path",
                "user_id": call_sid,
                "session_id": doc_id,
                "state_json": json.dumps(memory_dict),
                "events_json": "[]",
                "updated_at": now
            }
            # Check if exists
            path = f"/collections/adk_sessions/documents/{doc_id}"
            exists = await self._motel_request("GET", path)
            if exists and not exists.get("code"): # _motel_request returns {"code": 404} on error
                await self._motel_request("PATCH", path, data={"data": data})
            else:
                post_path = "/collections/adk_sessions/documents"
                await self._motel_request("POST", post_path, data={"documentId": doc_id, "data": data})
            logger.debug(f"💾 Hot path state saved for {call_sid}")
        except Exception as e:
            logger.error(f"Failed to save hot path state for {call_sid}: {e}")

    async def get_hot_path_state(self, call_sid: str) -> dict:
        """Fetch ephemeral hot-path state from adk_sessions."""
        try:
            doc_id = f"hp_{call_sid}"
            path = f"/collections/adk_sessions/documents/{doc_id}"
            doc = await self._motel_request("GET", path)
            if doc and "state_json" in doc:
                return json.loads(doc["state_json"])
        except Exception as e:
            logger.debug(f"No hot path state found for {call_sid} (or error: {e})")
        return {}

    async def delete_hot_path_state(self, call_sid: str) -> None:
        """Delete the ephemeral hot-path state from adk_sessions upon call termination."""
        try:
            doc_id = f"hp_{call_sid}"
            path = f"/collections/adk_sessions/documents/{doc_id}"
            await self._motel_request("DELETE", path)
            logger.debug(f"🧹 Hot path state cleaned up for {call_sid}")
        except Exception as e:
            # We don't error loudly on a 404 if it was already deleted or didn't exist
            logger.debug(f"Failed to delete hot path state for {call_sid} (likely not found): {e}")
