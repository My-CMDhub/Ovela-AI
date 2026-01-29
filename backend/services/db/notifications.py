from datetime import datetime
from zoneinfo import ZoneInfo
from appwrite.id import ID
import json
import requests
import logging

logger = logging.getLogger(__name__)

class NotificationsMixin:
    """
    Handles Staff Notifications and System Alerts.
    """
    
    def create_staff_notification(self, notification_type: str, customer_name: str, 
                                   customer_phone: str, reason: str, 
                                   urgency: str = "medium", extra_data: dict = None,
                                   tenant_id: str = "coalcreek") -> dict:
        """
        Create a staff notification (callback request, approval needed, etc).
        """
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            doc_id = ID.unique()
            now = datetime.now(MELBOURNE_TZ).isoformat()
            
            data = {
                "type": notification_type,  # callback_request, booking_approval, complaint, etc.
                "status": "pending",  # pending, in_progress, completed, dismissed
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "reason": reason,
                "urgency": urgency,  # low, medium, high
                "staff_notes": "",
                "extra_data": json.dumps(extra_data or {}),
                "tenant_id": tenant_id,  # Multi-tenant support
                "created_at": now,
                "updated_at": now,
                "completed_at": ""
            }
            
            result = self._make_request(
                "POST",
                f"/databases/{self.motel_db_id}/collections/staff_notifications/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"Created staff notification: {doc_id} - {notification_type}")
            return result
        except Exception as e:
            logger.error(f"Error creating staff notification: {e}")
            return None
    
    def get_staff_notifications(self, status: str = None, notification_type: str = None, limit: int = 50) -> list:
        """Get staff notifications with optional filters."""
        try:
            result = self._make_request(
                "GET",
                f"/databases/{self.motel_db_id}/collections/staff_notifications/documents"
            )
            notifications = result.get("documents", []) if result else []
            
            # Filter in Python for reliability
            if status:
                notifications = [n for n in notifications if n.get("status") == status]
            if notification_type:
                notifications = [n for n in notifications if n.get("type") == notification_type]
            
            # Sort by created_at descending (newest first)
            notifications.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            return notifications[:limit]
        except Exception as e:
            logger.error(f"Error fetching staff notifications: {e}")
            return []
    
    def update_staff_notification(self, notification_id: str, data: dict) -> dict:
        """Update a staff notification (change status, add notes)."""
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            data["updated_at"] = datetime.now(MELBOURNE_TZ).isoformat()
            
            # If completing, set completed_at
            if data.get("status") == "completed":
                data["completed_at"] = data["updated_at"]
            
            result = self._make_request(
                "PATCH",
                f"/databases/{self.motel_db_id}/collections/staff_notifications/documents/{notification_id}",
                data={"data": data}
            )
            logger.info(f"Updated staff notification: {notification_id}")
            return result
        except Exception as e:
            logger.error(f"Error updating staff notification: {e}")
            return None
    
    def delete_staff_notification(self, notification_id: str) -> bool:
        """Delete a staff notification."""
        try:
            url = f"{self.endpoint}/databases/{self.motel_db_id}/collections/staff_notifications/documents/{notification_id}"
            headers = {
                'X-Appwrite-Project': self.project_id,
                'X-Appwrite-Key': self.api_key
            }
            response = requests.delete(url, headers=headers)
            response.raise_for_status()
            logger.info(f"Deleted staff notification: {notification_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting staff notification: {e}")
            return False

    def create_system_alert(self, 
                          title: str,
                          message: str,
                          severity: str = "warning", # info, warning, error, critical
                          component: str = "voice_agent",
                          tenant_id: str = "default",
                          metadata: dict = None) -> dict:
        """
        Create a system alert for the staff notification center.
        Used for visible error tracking (Ghosting, API failures).
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
                "status": "new",  # new, acknowledged, resolved
                "metadata_json": json.dumps(metadata) if metadata else "{}",
                "created_at": now
            }
            
            # Note: Ensure 'system_alerts' collection exists in Appwrite
            result = self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/system_alerts/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"🚨 System Alert Created: {title}")
            return result
        except Exception as e:
            # Fallback log if alert creation fails (don't crash app)
            logger.error(f"Failed to create system alert: {e}")
            return None
