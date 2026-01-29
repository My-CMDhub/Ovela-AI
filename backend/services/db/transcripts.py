import json
from datetime import datetime
from zoneinfo import ZoneInfo
from appwrite.id import ID
import logging

logger = logging.getLogger(__name__)

class TranscriptsMixin:
    """
    Handles Call Transcripts, Demo Transcripts, and Call Logs.
    """

    # Tenant isolation: Each client gets their own transcript collection
    TENANT_TRANSCRIPT_COLLECTIONS = {
        "coalcreek": "call_transcripts_coalcreek",
        "saranda": "call_transcripts_saranda",
        # Future tenants:
        # "lydoun": "call_transcripts_lydoun",
    }
    
    def get_transcript_collection_for_tenant(self, tenant_id: str) -> str:
        """
        Get the transcript collection ID for a specific tenant.
        Raises ValueError if tenant is not configured (strict isolation).
        """
        if tenant_id not in self.TENANT_TRANSCRIPT_COLLECTIONS:
            raise ValueError(f"Unknown tenant for transcript storage: {tenant_id}")
        return self.TENANT_TRANSCRIPT_COLLECTIONS[tenant_id]

    def create_demo_transcript(self, phone: str, transcript: list, 
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
                "tenant_id": tenant_id,  # Multi-tenant support
                "created_at": now
            }
            
            result = self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/demo_transcripts/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"Created demo transcript: {doc_id} ({exchange_count} exchanges)")
            return result
        except Exception as e:
            logger.error(f"Error creating demo transcript: {e}")
            return None
    
    def update_transcript_feedback(self, transcript_id: str, feedback: str, 
                                    score: int = None, issues: list = None):
        """Update transcript with Mistral's AI feedback."""
        try:
            data = {
                "ai_feedback": feedback
            }
            if score is not None:
                data["feedback_score"] = score
            if issues:
                data["issues_found"] = json.dumps(issues)
            
            result = self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/demo_transcripts/documents/{transcript_id}",
                data={"data": data}
            )
            logger.info(f"Updated transcript feedback: {transcript_id}")
            return result
        except Exception as e:
            logger.error(f"Error updating transcript feedback: {e}")
            return None
    
    def get_transcripts_for_review(self, limit: int = 20):
        """Get transcripts that haven't been reviewed yet (no AI feedback)."""
        try:
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/demo_transcripts/documents"
            )
            if result and result.get("documents"):
                return [t for t in result["documents"] if not t.get("ai_feedback")][:limit]
            return []
        except Exception as e:
            logger.error(f"Error fetching transcripts for review: {e}")
            return []
    
    def get_call_transcripts(self, start_date: str = None, end_date: str = None, 
                             phone: str = None, limit: int = 100) -> list:
        """
        Get call transcripts with optional filters (DEMO calls).
        """
        try:
            path = f"/databases/{self.db_id}/collections/demo_transcripts/documents"
            
            queries = [
                'orderDesc("created_at")',
                f'limit({limit})'
            ]
            
            if start_date:
                queries.append(f'greaterThanEqual("created_at", "{start_date}")')
            if end_date:
                queries.append(f'lessThanEqual("created_at", "{end_date}")')
            if phone:
                queries.append(f'equal("phone", "{phone}")')
                
            params = {'queries': queries}
            
            result = self._make_request("GET", path, params=params)
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching transcripts: {e}")
            return []
    
    def save_call_transcript(
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
        """
        Save a call transcript to tenant-specific collection.
        Enforces strict tenant isolation.
        """
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            collection_id = self.get_transcript_collection_for_tenant(tenant_id)
            doc_id = ID.unique()
            now = datetime.now(MELBOURNE_TZ).isoformat()
            
            data = {
                "call_sid": call_sid,
                "caller_phone": caller_phone or "",
                "transcript": transcript[:10000] if transcript else "",  # Max 10k chars
                "duration": duration or 0,
                "booking_ref": booking_ref or "",
                "status": status or "",
                "room_type": room_type or "",
                "metadata_json": json.dumps(metadata) if metadata else "{}",
                "created_at": now
            }
            
            result = self._make_request(
                "POST",
                f"/databases/{self.motel_db_id}/collections/{collection_id}/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"Saved transcript for {tenant_id}: {doc_id}")
            return result
        except ValueError as e:
            logger.error(f"Tenant isolation error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error saving call transcript: {e}")
            return None

    def get_tenant_call_logs(
        self,
        tenant_id: str,
        limit: int = 50,
        start_date: str = None,
        end_date: str = None,
        phone: str = None
    ) -> list:
        """
        Get call logs for a specific tenant.
        Returns newest first.
        """
        try:
            collection_id = self.get_transcript_collection_for_tenant(tenant_id)
            
            result = self._make_request(
                "GET",
                f"/databases/{self.motel_db_id}/collections/{collection_id}/documents"
            )
            
            logs = result.get("documents", []) if result else []
            
            # Filter by date if provided
            if start_date:
                logs = [l for l in logs if l.get("created_at", "") >= start_date]
            if end_date:
                logs = [l for l in logs if l.get("created_at", "") <= end_date]

            # Filter by phone if provided (Search)
            if phone:
                logs = [l for l in logs if phone in l.get("caller_phone", "")]
            
            # Sort by created_at descending (newest first)
            logs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            return logs[:limit]
        except ValueError as e:
            logger.error(f"Tenant isolation error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching tenant call logs: {e}")
            return []
