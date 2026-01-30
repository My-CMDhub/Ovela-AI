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

    async def find_customers_by_name(self, name_query: str, tenant_id: str, limit: int = 5):
        """
        Find customers by partial name match.
        Priority: 
        1. 'customers' collection (CRM profile)
        2. 'call_transcripts_{tenant}' collection (Historical Callers)
        """
        results = []
        
        # 1. Search Primary 'customers' collection
        try:
            path = f"/databases/{self.db_id}/collections/customers/documents"
            queries = [
                f'search("name", "{name_query}")',
                f'equal("tenant_id", "{tenant_id}")',
                f'limit({limit})'
            ]
            
            response = await self._make_request("GET", path, params={"queries": queries})
            if response and response.get("documents"):
                 results = response.get("documents")
        except Exception as e:
            # It's okay if this fails (e.g. collection doesn't exist yet)
            pass

        # 2. Fallback: Search Transcripts (if no CRM results)
        if not results:
            try:
                # Resolve transcript collection name
                # Simple mapping based on known tenants, defaults to call_transcripts_{tenant_id}
                coll_name = f"call_transcripts_{tenant_id}"
                
                # Check for "Not provided" or generic names to avoid junk
                if name_query.lower() in ["unknown", "guest", "not provided"]:
                    return []

                path = f"/databases/{self.motel_db_id}/collections/{coll_name}/documents"
                # queries = [
                #     'limit(100)' 
                # ]
                queries = []
                
                response = await self._make_request("GET", path, params={"queries": queries})
                transcripts = response.get("documents", []) if response else []
                
                # Setup Deduplication by Phone
                seen_phones = set()
                name_lower = name_query.lower()
                
                for t in transcripts:
                    # Python Filter
                    c_name = t.get("customer_name", "")
                    if not c_name or name_lower not in c_name.lower():
                        continue
                        
                    name = c_name
                    phone = t.get("caller_phone")
                    
                    if not name or not phone: continue
                    if phone in seen_phones: continue
                    
                    # Transform to Customer format
                    results.append({
                        "name": name,
                        "phone": phone,
                        "tenant_id": tenant_id,
                        "$id": t.get("$id"), # Use transcript ID as proxy
                        "source": "transcript", 
                        "sms_status": t.get("sms_status")
                    })
                    seen_phones.add(phone)
                    
                    if len(results) >= limit:
                        break
                        
            except Exception as e:
                logger.warning(f"Transcript fallback search failed: {e}")
        
        return results

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
