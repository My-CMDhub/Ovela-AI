import json
import logging

logger = logging.getLogger(__name__)

from appwrite.query import Query as AppwriteQuery
class SettingsMixin:
    """
    Handles Business/Tenant Settings.
    """

    async def get_business(self, whatsapp_business_id: str):
        """Fetch business settings by WhatsApp Business ID."""
        try:
            queries = [AppwriteQuery.equal("whatsapp_business_id", whatsapp_business_id)]
            params = {'queries': queries}
            
            result = await self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/businesses/documents",
                params=params
            )
            
            if result and result.get('documents'):
                return result['documents'][0]
            return None
        except Exception as e:
            logger.error(f"Error fetching business: {e}")
            return None

    async def get_business_by_id(self, business_id: str):
        """Get business settings by document ID."""
        try:
            result = await self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/businesses/documents/{business_id}"
            )
            return result
        except Exception as e:
            logger.error(f"Error fetching business by ID: {e}")
            return None

    async def upsert_business(self, business_id: str, name: str, industry: str, settings_json: str = "{}", owner_email: str = "", business_phone: str = ""):
        """Create or update business settings."""
        try:
            # Try to get existing business
            existing = await self.get_business_by_id(business_id)
            
            data = {
                "name": name,
                "industry": industry,
                "whatsapp_business_id": business_id,  # Use same ID for lookup
                "system_prompt_override": settings_json,  # Store all settings as JSON
                "owner_email": owner_email,  # Also store separately for quick access
                "business_phone": business_phone  # Also store separately for quick access
            }
            
            if existing:
                # Update existing
                result = await self._make_request(
                    "PATCH",
                    f"/databases/{self.db_id}/collections/businesses/documents/{business_id}",
                    data={"data": data}
                )
            else:
                # Create new
                result = await self._make_request(
                    "POST",
                    f"/databases/{self.db_id}/collections/businesses/documents",
                    data={
                        "documentId": business_id,
                        "data": data
                    }
                )
            
            return result
        except Exception as e:
            logger.error(f"Error upserting business: {e}")
            return None

    async def get_all_settings(self):
        """Get settings for the default business (for AI prompt building)."""
        business = await self.get_business_by_id("default_business")
        if business:
            try:
                settings = json.loads(business.get("system_prompt_override", "{}"))
                return {
                    "business_name": business.get("name", ""),
                    "industry": business.get("industry", "beauty"),
                    **settings
                }
            except:
                return {"business_name": business.get("name", ""), "industry": business.get("industry", "beauty")}
        return None

    async def get_tenant_settings(self, tenant_id: str) -> dict:
        """
        Get tenant settings from the 'tenants' collection.
        Returns a dictionary with business info.
        """
        try:
            path = f"/databases/{self.motel_db_id}/collections/tenants/documents/{tenant_id}"
            
            result = await self._make_request("GET", path)
            
            if not result:
                # Fallback: Query by slug if doc ID lookup failed
                params = {
                    "queries": [AppwriteQuery.equal("slug", tenant_id)]
                }
                list_result = await self._make_request(
                    "GET", 
                    f"/databases/{self.motel_db_id}/collections/tenants/documents",
                    params=params
                )
                if list_result and list_result.get("documents"):
                    result = list_result["documents"][0]
            
            if not result:
                return None
                
            config = {}
            if result.get("config"):
                try:
                    config = json.loads(result["config"])
                except:
                    config = {}
            
            return {
                "business_name": result.get("name") or result.get("business_name", ""),
                "business_hours": result.get("business_hours") or config.get("business_hours", ""),
                "location": result.get("location") or config.get("location", ""),
                "business_phone": result.get("business_phone") or result.get("twilio_phone", ""),
                "owner_email": result.get("owner_email") or result.get("staff_email") or config.get("staff_email", ""),
                "staff_email": result.get("staff_email") or config.get("staff_email", "")
            }
            
        except Exception as e:
            logger.error(f"Error fetching tenant settings for {tenant_id}: {e}")
            return None

    async def update_tenant_settings(self, tenant_id: str, settings_data: dict) -> bool:
        """
        Update tenant document in 'tenants' collection.
        """
        try:
            payload = {
                "name": settings_data.get("business_name"),
                "business_hours": settings_data.get("business_hours"),
                "location": settings_data.get("location"),
                "business_phone": settings_data.get("business_phone"),
                "owner_email": settings_data.get("owner_email"),
                "staff_email": settings_data.get("staff_email")
            }
            
            body = {"data": payload}
            path = f"/databases/{self.motel_db_id}/collections/tenants/documents/{tenant_id}"
            result = await self._make_request("PATCH", path, data=body)
            
            return result is not None
        except Exception as e:
            logger.error(f"Error updating tenant settings for {tenant_id}: {e}")
            return False

    async def get_tenant_config(self, tenant_id: str) -> dict:
        """
        Get full tenant configuration for Voice Agent.
        """
        try:
            path = f"/databases/{self.motel_db_id}/collections/tenants/documents/{tenant_id}"
            result = await self._make_request("GET", path)
            
            if not result:
                params = {"queries": [AppwriteQuery.equal("slug", tenant_id)]}
                list_result = await self._make_request("GET", f"/databases/{self.motel_db_id}/collections/tenants/documents", params=params)
                if list_result and list_result.get("documents"):
                    result = list_result["documents"][0]
            
            if not result:
                return {}

            config = {}
            if result.get("config"):
                try:
                    config = json.loads(result["config"])
                except:
                    config = {}
            
            config["tenant_id"] = tenant_id
            config["business_name"] = result.get("name")
            config["twilio_phone"] = result.get("twilio_phone")
            config["business_phone"] = result.get("business_phone")
            config["staff_email"] = result.get("staff_email")
            
            if "integrations" not in config:
                config["integrations"] = {}
            
            if result.get("pms_provider"):
                config["integrations"]["pms_provider"] = result.get("pms_provider")
                config["pms_provider"] = result.get("pms_provider")
            
            return config
            
        except Exception as e:
            logger.error(f"Error fetching tenant config for {tenant_id}: {e}")
            return {}
