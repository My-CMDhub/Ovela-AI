"""
Staff Notification Service
Handles sending alerts and requests to staff members.
"""
import logging
from services.email import email_service
from services.appwrite import db_service
from core.config import settings

logger = logging.getLogger(__name__)

class StaffNotificationService:
    def __init__(self):
        self.default_staff_email = settings.STAFF_NOTIFICATION_RECIPIENTS or "getnewone2022@gmail.com"

    async def notify_new_callback_request(self, 
                                        customer_phone: str, 
                                        customer_name: str, 
                                        reason: str,
                                        urgency: str = "medium") -> bool:
        """
        Notify staff that a customer requested a callback.
        Also saves to database for tracking, and includes magic link action buttons.
        """
        try:
            # 1. Save to database first (for tracking)
            db_result = db_service.create_staff_notification(
                notification_type="callback_request",
                customer_name=customer_name,
                customer_phone=customer_phone,
                reason=reason,
                urgency=urgency
            )
            
            # Get the notification ID for magic links
            notification_id = db_result.get("$id") if db_result else None
            
            # 2. Send email notification with magic link action buttons
            recipient = self.default_staff_email
            
            success = await email_service.send_human_callback_request(
                owner_email=recipient,
                customer_name=customer_name,
                customer_phone=customer_phone,
                reason=reason,
                urgency=urgency,
                notification_id=notification_id  # For magic link buttons
            )
            
            if success:
                logger.info(f"Callback request sent for {customer_name} ({customer_phone})")
            else:
                logger.error(f"Failed to send callback email for {customer_name}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in notify_new_callback_request: {e}")
            return False

staff_notification_service = StaffNotificationService()
