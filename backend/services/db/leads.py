from datetime import datetime, timedelta
import logging
from typing import Optional, Any, Dict
from appwrite.id import ID
from core.utils import mask_phone

logger = logging.getLogger(__name__)

class LeadsMixin:
    """
    Handles Demo Leads and CRM Contacts.
    ENFORCED: Multi-tenant isolation at DB level.
    """

    async def create_demo_lead(
        self,
        phone: str,
        name: str = None,
        tenant_id: str = "ovela_demo",
        business_name: str = None,
        source: str = "website",
    ):
        """Create a new lead from a demo request."""
        try:
            doc_id = ID.unique()
            data = {
                "phone": phone,
                "name": name or "Anonymous",
                "tenant_id": tenant_id,
                "created_at": datetime.now().isoformat(),
                "status": "new",
            }
            if business_name is not None:
                data["business_name"] = business_name
            if source:
                data["source"] = source
            
            result = await self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/demo_leads/documents",
                data={
                    "documentId": doc_id,
                    "data": data
                }
            )
            
            logger.info(f"Created demo lead: {doc_id} for {mask_phone(phone)} (Tenant: {tenant_id})")
            return result
        except Exception as e:
            logger.error(f"Error creating lead: {e}")
            return None

    async def check_demo_limit(self, phone: str, tenant_id: str = "ovela_demo", limit_per_hour: int = 3) -> bool:
        """
        Check if a phone number has exceeded demo limits.
        ENFORCED: Server-side filtering by phone and tenant.
        """
        try:
            path = f"/databases/{self.db_id}/collections/demo_leads/documents"
            
            # Use Appwrite queries for server-side filtering
            queries = [
                f'equal("phone", "{phone}")',
                f'equal("tenant_id", "{tenant_id}")',
                'orderDesc("created_at")',
                'limit(10)'
            ]
            
            result = await self._make_request("GET", path, params={"queries": queries})
            leads = result.get("documents", []) if result else []
            
            if not leads:
                return True # No prior leads, ok to proceed
            
            # Check recent leads within the last hour
            hour_ago = datetime.now() - timedelta(hours=1)
            recent_count = 0
            for lead in leads:
                created_at_str = lead.get("created_at")
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str)
                    if created_at > hour_ago:
                        recent_count += 1
            
            return recent_count < limit_per_hour
            
        except Exception as e:
            logger.error(f"Error checking demo limit for {mask_phone(phone)}: {e}")
            return True # Allow on error to avoid blocking users, but log it

    async def get_recent_leads(self, tenant_id: str, limit: int = 10):
        """Get recent leads for a tenant."""
        try:
            path = f"/databases/{self.db_id}/collections/demo_leads/documents"
            queries = [
                f'equal("tenant_id", "{tenant_id}")',
                'orderDesc("created_at")',
                f'limit({limit})'
            ]
            result = await self._make_request("GET", path, params={"queries": queries})
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching leads: {e}")
            return []

    async def update_lead_status(self, lead_id: str, status: str):
        """Update a lead's status (e.g. called, converted)."""
        try:
            return await self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/demo_leads/documents/{lead_id}",
                data={"data": {"status": status}}
            )
        except Exception as e:
            logger.error(f"Error updating lead status: {e}")
            return None

    async def get_demo_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single demo lead by document id."""
        return await self._make_request(
            "GET",
            f"/databases/{self.db_id}/collections/demo_leads/documents/{lead_id}",
        )

    async def update_demo_lead(self, lead_id: str, data: dict) -> Optional[Dict[str, Any]]:
        """Merge-partial update for demo lead attributes (Appwrite data payload)."""
        if not data:
            return None
        try:
            return await self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/demo_leads/documents/{lead_id}",
                data={"data": data},
            )
        except Exception as e:
            logger.error(f"Error updating demo lead {lead_id}: {e}")
            return None
