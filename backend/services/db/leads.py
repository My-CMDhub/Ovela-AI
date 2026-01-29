from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from appwrite.id import ID
from rules.whitelist import is_whitelisted
import logging

logger = logging.getLogger(__name__)

class LeadsMixin:
    """
    Handles Demo Leads and rate limiting for them.
    """
    
    DEMO_LIMIT_HOURS = 24 # One demo per day

    def create_demo_lead(self, name: str, business_name: str, phone: str, source: str = "website") -> dict:
        """Create a new demo lead when form is submitted."""
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            doc_id = ID.unique()
            now = datetime.now(MELBOURNE_TZ).isoformat()
            
            data = {
                "name": name,
                "business_name": business_name,
                "phone": phone,
                "status": "pending",
                "source": source,
                "created_at": now,
                "updated_at": now
            }
            
            result = self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/demo_leads/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"Created demo lead: {doc_id} for {phone}")
            return result
        except Exception as e:
            logger.error(f"Error creating demo lead: {e}")
            return None
    
    def get_demo_lead(self, lead_id: str) -> dict:
        """Get a single demo lead by ID."""
        try:
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/demo_leads/documents/{lead_id}"
            )
            return result
        except Exception as e:
            logger.error(f"Error getting demo lead {lead_id}: {e}")
            return None
    
    def update_demo_lead(self, lead_id: str = None, phone: str = None, data: dict = None):
        """Update a demo lead by ID or phone."""
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            # Find by phone if ID not provided
            if not lead_id and phone:
                result = self._make_request(
                    "GET",
                    f"/databases/{self.db_id}/collections/demo_leads/documents"
                )
                if result and result.get("documents"):
                    for doc in result["documents"]:
                        if doc.get("phone") == phone:
                            lead_id = doc.get("$id")
                            break
            
            if not lead_id:
                logger.warning(f"Demo lead not found for phone: {phone}")
                return None
            
            data["updated_at"] = datetime.now(MELBOURNE_TZ).isoformat()
            
            result = self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/demo_leads/documents/{lead_id}",
                data={"data": data}
            )
            return result
        except Exception as e:
            # Handle 404 gracefully (document already deleted or not found)
            if "404" in str(e):
                logger.warning(f"Demo lead not found for update: {lead_id or phone}")
                return None
            logger.error(f"Error updating demo lead: {e}")
            return None
    
    def check_demo_limit(self, phone: str) -> bool:
        """
        Check if phone number has already requested a demo in the last 24 hours.
        Returns: True if allowed, False if blocked.
        """
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            
            # Check whitelist first
            if is_whitelisted(phone):
                return True
                
            # Calculate time threshold
            now = datetime.now(MELBOURNE_TZ)
            threshold = now - timedelta(hours=self.DEMO_LIMIT_HOURS)
            threshold_str = threshold.isoformat()
            
            # Fetch all demo leads and filter in-memory for reliability
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/demo_leads/documents"
            )
            
            if result and result.get("documents"):
                for doc in result["documents"]:
                    if doc.get("phone") == phone:
                        created_at = doc.get("created_at", "")
                        if created_at > threshold_str:
                            logger.info(f"Rate limit: {phone} already requested demo at {created_at}")
                            return False
            return True
            
        except Exception as e:
            logger.error(f"Error checking demo limit: {e}")
            return True # Fail open
