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

    async def notify_new_booking_request(self,
                                        guest_name: str,
                                        guest_phone: str,
                                        guest_email: str,  # Added for guest confirmation
                                        check_in: str,
                                        check_out: str,
                                        room_type: str,
                                        total_amount: float,
                                        booking_reference: str,
                                        num_nights: int = 1) -> bool:
        """
        Notify staff about a new booking request that needs approval.
        Creates DB entry and sends email with approve/reject buttons.
        Stores booking data for guest confirmation on approval.
        """
        try:
            # Build reason text for notification
            reason = f"Booking: {room_type.title()} Room, {check_in} to {check_out} ({num_nights} nights), ${total_amount}"
            
            # Extra data for guest confirmation when approved
            extra_data = {
                "booking_reference": booking_reference,
                "guest_email": guest_email,
                "check_in": check_in,
                "check_out": check_out,
                "room_type": room_type,
                "total_amount": total_amount,
                "num_nights": num_nights
            }
            
            # 1. Save to database with extra_data
            db_result = db_service.create_staff_notification(
                notification_type="booking_approval",
                customer_name=guest_name,
                customer_phone=guest_phone,
                reason=reason,
                urgency="high",
                extra_data=extra_data  # Store for guest confirmation
            )
            
            notification_id = db_result.get("$id") if db_result else None
            
            # 2. Send email
            recipient = self.default_staff_email
            
            success = await email_service.send_booking_approval_request(
                owner_email=recipient,
                guest_name=guest_name,
                guest_phone=guest_phone,
                check_in=check_in,
                check_out=check_out,
                room_type=room_type,
                total_amount=total_amount,
                booking_reference=booking_reference,
                num_nights=num_nights,
                notification_id=notification_id
            )
            
            if success:
                logger.info(f"Booking approval request sent for {guest_name} ({booking_reference})")
            else:
                logger.error(f"Failed to send booking email for {guest_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in notify_new_booking_request: {e}")
            return False

staff_notification_service = StaffNotificationService()
