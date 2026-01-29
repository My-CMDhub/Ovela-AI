import json
from datetime import datetime
from zoneinfo import ZoneInfo
from appwrite.id import ID
from appwrite.query import Query as AppwriteQuery
import logging
from core.utils import mask_phone

logger = logging.getLogger(__name__)

class TranscriptsMixin:
    """
    Handles Call Transcripts, Demo Transcripts, and Call Logs.
    """

    # Tenant isolation: Each client gets their own transcript collection
    TENANT_TRANSCRIPT_COLLECTIONS = {
        "coalcreek": "call_transcripts_coalcreek",
        "saranda": "call_transcripts_saranda",
    }
    
    async def get_transcript_collection_for_tenant(self, tenant_id: str) -> str:
        """
        Get the transcript collection ID for a specific tenant.
        """
        if tenant_id not in self.TENANT_TRANSCRIPT_COLLECTIONS:
            # Check if it's already a collection ID or log warning
            if tenant_id.startswith("call_transcripts_"):
                return tenant_id
            raise ValueError(f"Unknown tenant for transcript storage: {tenant_id}")
        return self.TENANT_TRANSCRIPT_COLLECTIONS[tenant_id]

    async def create_demo_transcript(self, phone: str, transcript: list, 
                                exchange_count: int = 0, duration_seconds: int = 0,
                                outcome: str = "completed", call_sid: str = None,
                                demo_lead_id: str = None, tenant_id: str = "ovela_demo") -> dict:
        """
        Store a demo call transcript for AI analysis.
        """
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            doc_id = ID.unique()
            now = datetime.now(MELBOURNE_TZ).isoformat()
            
            data = {
                "phone": phone,
                "transcript_json": json.dumps(transcript),
                "exchange_count": exchange_count,
                "duration_seconds": duration_seconds,
                "outcome": outcome,
                "call_sid": call_sid or "",
                "demo_lead_id": demo_lead_id or "",
                "tenant_id": tenant_id,
                "created_at": now
            }
            
            result = await self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/demo_transcripts/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"Created demo transcript: {doc_id} for {mask_phone(phone)}")
            return result
        except Exception as e:
            logger.error(f"Error creating demo transcript: {e}")
            return None
    
    async def update_transcript_feedback(self, transcript_id: str, feedback: str, 
                                    score: int = None, issues: list = None):
        """Update transcript with AI feedback."""
        try:
            data = {
                "ai_feedback": feedback
            }
            if score is not None:
                data["feedback_score"] = score
            if issues:
                data["issues_found"] = json.dumps(issues)
            
            result = await self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/demo_transcripts/documents/{transcript_id}",
                data={"data": data}
            )
            return result
        except Exception as e:
            logger.error(f"Error updating transcript feedback: {e}")
            return None
    
    async def get_call_transcripts(self, start_date: str = None, end_date: str = None, 
                             phone: str = None, limit: int = 100) -> list:
        """Get call transcripts with optional filters (DEMO calls)."""
        try:
            path = f"/databases/{self.db_id}/collections/demo_transcripts/documents"
            queries = [AppwriteQuery.order_desc("created_at"), AppwriteQuery.limit(limit)]
            
            if start_date:
                queries.append(AppwriteQuery.greater_than_equal("created_at", start_date))
            if end_date:
                queries.append(AppwriteQuery.less_than_equal("created_at", end_date))
            if phone:
                queries.append(AppwriteQuery.equal("phone", phone))
                
            result = await self._make_request("GET", path, params={'queries': queries})
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching transcripts: {e}")
            return []
    
    async def save_call_transcript(
        self,
        tenant_id: str,
        call_sid: str,
        caller_phone: str,
        transcript: str,
        duration: int,
        booking_ref: str = None,
        status: str = None,
        room_type: str = None,
        metadata: dict = None
    ) -> dict:
        """Save a call transcript to tenant-specific collection."""
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            collection_id = await self.get_transcript_collection_for_tenant(tenant_id)
            doc_id = ID.unique()
            now = datetime.now(MELBOURNE_TZ).isoformat()
            
            # STANDARDIZED SCHEMA (Consistent across all tenants)
            data = {
                "call_sid": call_sid,
                "caller_phone": caller_phone or "",
                "transcript_json": transcript, 
                "duration_seconds": duration or 0,
                "outcome": status or "completed",
                "pms_reference": booking_ref or "",
                "metadata_json": json.dumps(metadata) if metadata else "{}",
                "created_at": now
            }

            # BACKWARD COMPATIBILITY for Coal Creek (until pms_reference is added to Appwrite)
            if tenant_id == "coalcreek":
                data["transcript"] = transcript[:10000] if transcript else ""
                data["duration"] = duration or 0
                data["booking_ref"] = booking_ref or ""
                data["status"] = status or ""
            
            result = await self._make_request(
                "POST",
                f"/databases/{self.motel_db_id}/collections/{collection_id}/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"✅ Saved transcript for {tenant_id}: {doc_id} {mask_phone(caller_phone)}")
            return result
        except Exception as e:
            logger.error(f"❌ Error saving transcript for {tenant_id}: {e}")
            return None

    async def get_tenant_call_logs(self, tenant_id: str, limit: int = 50, start_date: str = None, end_date: str = None, phone: str = None) -> list:
        """Get call logs for a specific tenant."""
        try:
            collection_id = await self.get_transcript_collection_for_tenant(tenant_id)
            queries = [AppwriteQuery.order_desc("created_at"), AppwriteQuery.limit(limit)]
            if start_date:
                queries.append(AppwriteQuery.greater_than_equal("created_at", start_date))
            if end_date:
                queries.append(AppwriteQuery.less_than_equal("created_at", end_date))
            
            # Tenant specific field names
            phone_field = "caller_phone" # Both schemas use this or similar?
            # saranda: caller_phone / motel: caller_phone. It matches.
            if phone:
                queries.append(AppwriteQuery.equal("caller_phone", phone))
                
            result = await self._make_request("GET", f"/databases/{self.motel_db_id}/collections/{collection_id}/documents", params={'queries': queries})
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching logs for {tenant_id}: {e}")
            return []
