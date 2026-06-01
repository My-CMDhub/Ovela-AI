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
        metadata: dict = None,
        call_summary: str = None,
        customer_name: str = None
    ) -> dict:
        """Save a call transcript to tenant-specific collection."""
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            collection_id = await self.get_transcript_collection_for_tenant(tenant_id)
            doc_id = ID.unique()
            now = datetime.now(MELBOURNE_TZ).isoformat()

            if tenant_id == "coalcreek":
                # Matches the actual Appwrite schema for call_transcripts_coalcreek
                data = {
                    "call_sid": call_sid or "",
                    "caller_phone": caller_phone or "",
                    "duration": duration or 0,
                    "booking_ref": booking_ref or "",
                    "status": status or "completed",
                    "room_type": room_type or "",
                    "transcript": (transcript[:10000] if transcript else ""),
                    "metadata_json": json.dumps(metadata) if metadata else "{}",
                    "created_at": now,
                }
            else:
                data = {
                    "call_sid": call_sid,
                    "caller_phone": caller_phone or "",
                    "duration_seconds": duration or 0,
                    "outcome": status or "completed",
                    "pms_reference": booking_ref or "",
                    "call_summary": call_summary or "",
                    "customer_name": customer_name or "Not provided",
                    "transcript_json": transcript,
                    "metadata_json": json.dumps(metadata) if metadata else "{}",
                    "created_at": now,
                }

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
            phone_field = "caller_phone"
            if phone:
                queries.append(AppwriteQuery.equal("caller_phone", phone))
                
            result = await self._make_request("GET", f"/databases/{self.motel_db_id}/collections/{collection_id}/documents", params={'queries': queries})
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching logs for {tenant_id}: {e}")
            return []

    async def get_daily_summary_stats(self, tenant_id: str) -> dict:
        """
        Get aggregated stats for the current day (Melbourne Time).
        Returns: {
            "total_calls": int,
            "missed_calls": int,
            "avg_duration": float
        }
        """
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            now = datetime.now(MELBOURNE_TZ)
            
            # Start of day in ISO format
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            
            # Get collection ID
            collection_id = await self.get_transcript_collection_for_tenant(tenant_id)
            
            # Query - Fetch all calls for today. 
            # Note: Appwrite Aggregations aren't fully exposed in simple API, 
            # so we fetch metadata and aggregate in python (efficient enough for <1000 calls/day).
            # We use limit=5000 to be safe.
            
            path = f"/databases/{self.motel_db_id}/collections/{collection_id}/documents"
            queries = [
                AppwriteQuery.greater_than_equal("created_at", start_of_day),
                AppwriteQuery.limit(5000) 
            ]
            
            # Execute request
            result = await self._make_request("GET", path, params={'queries': queries})
            docs = result.get("documents", []) if result else []
            
            total = len(docs)
            
            # Calculate metrics
            # Missed: outcome in ISSUE_OUTCOMES or duration < 3
            # ISSUE_OUTCOMES: ["spam_terminated", "timeout_silence", "timeout_duration", "abuse_timeout"]
            
            issue_outcomes = ["spam_terminated", "timeout_silence", "timeout_duration", "abuse_timeout"]
            
            missed_count = 0
            total_duration = 0
            
            for doc in docs:
                outcome = doc.get("outcome") or doc.get("status", "")
                duration = doc.get("duration_seconds") or doc.get("duration", 0)
                
                total_duration += duration
                
                if outcome in issue_outcomes or duration < 3:
                     missed_count += 1
            
            avg_duration = total_duration / total if total > 0 else 0
            
            return {
                "total_calls": total,
                "missed_calls": missed_count,
                "avg_duration": avg_duration
            }
            
        except Exception as e:
            logger.error(f"Error getting daily stats for {tenant_id}: {e}")
            return {
                "total_calls": 0,
                "missed_calls": 0,
                "avg_duration": 0
            }
    async def update_call_log_by_sid(self, tenant_id: str, call_sid: str, updates: dict) -> bool:
        """
        Update a call log document by its CallSid.
        Used for async updates like "SMS Sent" or "Order Confirmed".
        """
        try:
            collection_id = await self.get_transcript_collection_for_tenant(tenant_id)
            
            # Find document by CallSid
            queries = [AppwriteQuery.equal("call_sid", call_sid)]
            params = {'queries': queries}
            
            result = await self._make_request(
                "GET", 
                f"/databases/{self.motel_db_id}/collections/{collection_id}/documents",
                params=params
            )
            
            if not result or not result.get("documents"):
                logger.warning(f"⚠️ Call Log not found for SID: {call_sid} (tenant: {tenant_id})")
                return False
                
            doc_id = result["documents"][0]["$id"]
            
            # Apply updates
            # Note: We wrap in "data" for Appwrite
            patch_result = await self._make_request(
                "PATCH",
                f"/databases/{self.motel_db_id}/collections/{collection_id}/documents/{doc_id}",
                data={"data": updates}
            )
            
            if patch_result:
                logger.info(f"✅ Updated call log {doc_id} with {updates.keys()}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating call log for {call_sid}: {e}")
            return False

    async def check_voice_rate_limit(self, phone: str, tenant_id: str = "coalcreek") -> tuple[bool, str]:
        """
        Enforce rate limiting on incoming voice calls:
        - Admin / Whitelisted numbers bypass all limits.
        - User-Level Limit: Max 2 calls/24hr (AEST-anchored).
        - Global Limit: Max 10 calls/hr globally (for non-whitelisted callers).
        
        Returns:
            (is_allowed, reason)
        """
        from datetime import timedelta
        from rules.whitelist import is_whitelisted
        
        # 1. Admin/Whitelisted check
        if is_whitelisted(phone):
            logger.info(f"🟢 Whitelisted phone {mask_phone(phone)} bypassed all voice rate limits.")
            return True, "whitelisted"
            
        try:
            collection_id = await self.get_transcript_collection_for_tenant(tenant_id)
            from datetime import timezone
            now_utc = datetime.now(timezone.utc)
            
            # --- 2. User-Level Limit Check ---
            # Max 2 calls / 24 hours (UTC comparison matching Appwrite's storage format)
            hour_24_ago = (now_utc - timedelta(hours=24)).isoformat()
            
            user_queries = [
                AppwriteQuery.equal("caller_phone", phone),
                AppwriteQuery.greater_than_equal("created_at", hour_24_ago),
                AppwriteQuery.limit(10)
            ]
            
            user_result = await self._make_request(
                "GET",
                f"/databases/{self.motel_db_id}/collections/{collection_id}/documents",
                params={'queries': user_queries}
            )
            
            user_docs = user_result.get("documents", []) if user_result else []
            valid_user_calls = [d for d in user_docs if d.get("status") != "blocked" and d.get("outcome") != "blocked"]
            
            if len(valid_user_calls) >= 2:
                logger.warning(f"🚫 User rate limit exceeded for {mask_phone(phone)}: {len(valid_user_calls)} calls in last 24h")
                return False, "user_limit_exceeded"
                
            # --- 3. Global Limit Check ---
            # Max 10 calls / hour globally (non-whitelisted)
            hour_ago = (now_utc - timedelta(hours=1)).isoformat()

            
            global_queries = [
                AppwriteQuery.greater_than_equal("created_at", hour_ago),
                AppwriteQuery.limit(50)
            ]
            
            global_result = await self._make_request(
                "GET",
                f"/databases/{self.motel_db_id}/collections/{collection_id}/documents",
                params={'queries': global_queries}
            )
            
            global_docs = global_result.get("documents", []) if global_result else []
            
            non_whitelisted_global_count = 0
            for doc in global_docs:
                doc_phone = doc.get("caller_phone")
                doc_status = doc.get("status") or doc.get("outcome")
                if doc_phone and not is_whitelisted(doc_phone) and doc_status != "blocked":
                    non_whitelisted_global_count += 1
                    
            if non_whitelisted_global_count >= 10:
                logger.warning(f"🚫 Global rate limit exceeded: {non_whitelisted_global_count} non-whitelisted calls in last hour")
                return False, "global_limit_exceeded"
                
            return True, "allowed"
            
        except Exception as e:
            logger.error(f"Error checking voice rate limit for {mask_phone(phone)}: {e}")
            # Fail-safe: allow on error to prevent blocking legitimate business, but log it
            return True, "error_fallback"

