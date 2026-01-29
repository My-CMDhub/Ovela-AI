from datetime import datetime
from zoneinfo import ZoneInfo
from appwrite.id import ID
import json
import logging
from core.utils import mask_phone

logger = logging.getLogger(__name__)

class NotificationsMixin:
    """
    Handles Staff Notifications and System Alerts.
    ENFORCED: Multi-tenant isolation at DB level.
    """
    
    async def create_staff_notification(self, notification_type: str, customer_name: str, 
                                   customer_phone: str, reason: str, 
                                   urgency: str = "medium", extra_data: dict = None,
                                   tenant_id: str = "coalcreek") -> dict:
        """
        Create a staff notification.
        """
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            doc_id = ID.unique()
            now = datetime.now(MELBOURNE_TZ).isoformat()
            
            data = {
                "type": notification_type,
                "status": "pending",
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "reason": reason,
                "urgency": urgency,
                "staff_notes": "",
                "extra_data": json.dumps(extra_data or {}),
                "tenant_id": tenant_id,
                "created_at": now,
                "updated_at": now,
                "completed_at": ""
            }
            
            result = await self._motel_request(
                "POST",
                f"/databases/{self.motel_db_id}/collections/staff_notifications/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"Created staff notification: {doc_id} - {notification_type} for {mask_phone(customer_phone)} (Tenant: {tenant_id})")
            return result
        except Exception as e:
            logger.error(f"Error creating staff notification: {e}")
            return None
    
    async def get_staff_notifications(self, status: str = None, notification_type: str = None, limit: int = 50, tenant_id: str = "coalcreek") -> list:
        """Get staff notifications with server-side tenant isolation."""
        try:
            queries = [f'equal("tenant_id", "{tenant_id}")']
            if status:
                queries.append(f'equal("status", "{status}")')
            if notification_type:
                queries.append(f'equal("type", "{notification_type}")')
            
            queries.append('orderDesc("created_at")')
            queries.append(f'limit({limit})')
            
            params = {"queries": queries}
            
            result = await self._motel_request(
                "GET",
                f"/databases/{self.motel_db_id}/collections/staff_notifications/documents",
                params=params
            )
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching staff notifications: {e}")
            return []
    
    async def update_staff_notification(self, notification_id: str, data: dict) -> dict:
        """Update a staff notification."""
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            data["updated_at"] = datetime.now(MELBOURNE_TZ).isoformat()
            
            if data.get("status") == "completed":
                data["completed_at"] = data["updated_at"]
            
            result = await self._motel_request(
                "PATCH",
                f"/databases/{self.motel_db_id}/collections/staff_notifications/documents/{notification_id}",
                data={"data": data}
            )
            return result
        except Exception as e:
            logger.error(f"Error updating staff notification: {e}")
            return None
    
    async def delete_staff_notification(self, notification_id: str) -> bool:
        """Delete a staff notification."""
        try:
            path = f"/databases/{self.motel_db_id}/collections/staff_notifications/documents/{notification_id}"
            result = await self._make_request("DELETE", path)
            return result is True
        except Exception as e:
            logger.error(f"Error deleting staff notification: {e}")
            return False

    async def create_system_alert(self, 
                          title: str,
                          message: str,
                          severity: str = "warning",
                          component: str = "voice_agent",
                          tenant_id: str = "default",
                          metadata: dict = None) -> dict:
        """
        Create a system alert.
        """
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            doc_id = ID.unique()
            now = datetime.now(MELBOURNE_TZ).isoformat()
            
            data = {
                "title": title,
                "message": message,
                "severity": severity,
                "component": component,
                "tenant_id": tenant_id,
                "status": "new",
                "metadata_json": json.dumps(metadata) if metadata else "{}",
                "created_at": now
            }
            
            result = await self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/system_alerts/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"🚨 System Alert Created: {title} (Tenant: {tenant_id})")
            return result
        except Exception as e:
            logger.error(f"Failed to create system alert: {e}")
            return None
