import logging
import json
from datetime import datetime
from appwrite.id import ID
from core.utils import mask_phone

logger = logging.getLogger(__name__)

class CustomersMixin:
    """
    Handles Customer Profiles and Stats.
    ENFORCED: Multi-tenant isolation for all operations.
    """

    async def find_customer_by_phone(self, phone: str, tenant_id: str):
        """
        Find a customer by phone number.
        ENFORCED: Scoped to tenant_id at the DB level.
        """
        try:
            path = f"/databases/{self.db_id}/collections/customers/documents"
            
            # Server-side scoping is critical here to prevent cross-tenant enumeration
            queries = [
                f'equal("phone", "{phone}")',
                f'equal("tenant_id", "{tenant_id}")',
                'limit(1)'
            ]
            
            result = await self._make_request("GET", path, params={"queries": queries})
            docs = result.get("documents", []) if result else []
            return docs[0] if docs else None
        except Exception as e:
            logger.error(f"Error finding customer {mask_phone(phone)}: {e}")
            return None

    async def create_customer(self, phone: str, name: str = None, tenant_id: str = "saranda"):
        """Create a new customer profile."""
        try:
            doc_id = ID.unique()
            data = {
                "phone": phone,
                "name": name or "Guest",
                "tenant_id": tenant_id,
                "created_at": datetime.now().isoformat(),
                "calls_count": 0,
                "preferences_json": json.dumps({})
            }
            
            result = await self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/customers/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"Created customer: {doc_id} {mask_phone(phone)} (Tenant: {tenant_id})")
            return result
        except Exception as e:
            logger.error(f"Error creating customer: {e}")
            return None

    async def update_customer_stats(self, phone: str, tenant_id: str, last_call_id: str = None, duration: int = 0):
        """Update interaction stats for a customer."""
        try:
            customer = await self.find_customer_by_phone(phone, tenant_id)
            
            if not customer:
                customer = await self.create_customer(phone, tenant_id=tenant_id)
            
            if not customer:
                return None

            cust_id = customer["$id"]
            count = customer.get("calls_count", 0) + 1
            
            # Update preferences/stats
            prefs = {}
            if customer.get("preferences_json"):
                try:
                    prefs = json.loads(customer["preferences_json"])
                except:
                    prefs = {}
            
            prefs["last_call_at"] = datetime.now().isoformat()
            if last_call_id:
                prefs["last_call_id"] = last_call_id
            
            # Basic analytics
            history = prefs.get("call_history", [])
            history.append({"id": last_call_id, "duration": duration, "at": prefs["last_call_at"]})
            prefs["call_history"] = history[-5:] # Keep last 5
            
            data = {
                "calls_count": count,
                "preferences_json": json.dumps(prefs)
            }
            
            return await self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/customers/documents/{cust_id}",
                data={"data": data}
            )
        except Exception as e:
            logger.error(f"Error updating customer stats: {e}")
            return None

    async def get_all_customers(self, tenant_id: str, limit: int = 100):
        """Get list of customers for a tenant."""
        try:
            path = f"/databases/{self.db_id}/collections/customers/documents"
            queries = [
                f'equal("tenant_id", "{tenant_id}")',
                'orderDesc("calls_count")',
                f'limit({limit})'
            ]
            result = await self._make_request("GET", path, params={"queries": queries})
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching customers: {e}")
            return []
