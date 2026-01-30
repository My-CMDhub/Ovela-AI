"""
Staff Notification Service
Handles sending alerts and requests to staff members.
"""
import logging
from services.email import email_service
from services.appwrite import db_service
from core.config import settings
from core.utils import mask_phone
import httpx
from twilio.rest import Client
import re

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
            db_result = await db_service.create_staff_notification(
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
                logger.info(f"Callback request sent for {customer_name} ({mask_phone(customer_phone)})")
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
            db_result = await db_service.create_staff_notification(
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
                notification_id=notification_id,
                guest_email=guest_email  # Include email in staff notification
            )
            
            if success:
                logger.info(f"Booking approval request sent for {guest_name} ({booking_reference})")
            else:
                logger.error(f"Failed to send booking email for {guest_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in notify_new_booking_request: {e}")
            return False

    # =========================================================================
    # SARANDA RESTAURANT - WhatsApp HITL Notifications
    # =========================================================================
    
    async def send_whatsapp_order_approval(self, *args, **kwargs) -> bool:
        """
        STUB: WhatsApp notifications are currently FROZEN/DISABLED.
        Always returns True to avoid breaking callers.
        """
        logger.info("❄️ WhatsApp notification suppressed (Feature Frozen)")
        return True

    async def _frozen_send_whatsapp_order_approval(
        self,
        request_id: str,
        request_type: str,  # "order", "change", "cancel", "reservation"
        customer_name: str,
        order_summary: str,
        pickup_time: str,
        total_amount: float = 0,
    ) -> bool:
        """
        [FROZEN] Send structured approval request to staff WhatsApp for Saranda.
        Staff replies with: YES, NO, or LATE
        
        Uses Twilio WhatsApp API (outbound from your Twilio number).
        """
        
        # 1. ATTEMPT META GRAPH API (Templates with Buttons)
        try:
            token = settings.META_ACCESS_TOKEN
            phone_number_id = settings.META_PHONE_NUMBER_ID
            staff_whatsapp = settings.SARANDA_STAFF_WHATSAPP
            clean_recipient = staff_whatsapp.lstrip("+")
            
            url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "messaging_product": "whatsapp",
                "to": clean_recipient,
                "type": "template",
                "template": {
                    "name": settings.WHATSAPP_TEMPLATE_NAME,
                    "language": {"code": "en"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": str(request_id)},
                                {"type": "text", "text": str(customer_name)},
                                {"type": "text", "text": str(order_summary)},
                                {"type": "text", "text": f"{total_amount:.2f}"},
                                {"type": "text", "text": str(pickup_time)}
                            ]
                        },
                        {
                            "type": "button",
                            "sub_type": "quick_reply",
                            "index": 0,
                            "parameters": [{"type": "payload", "payload": f"APPROVE_{request_id}"}]
                        },
                        {
                            "type": "button",
                            "sub_type": "quick_reply",
                            "index": 1,
                            "parameters": [{"type": "payload", "payload": f"REJECT_{request_id}"}]
                        },
                        {
                            "type": "button",
                            "sub_type": "quick_reply",
                            "index": 2,
                            "parameters": [{"type": "payload", "payload": f"LATE_{request_id}"}]
                        }
                    ]
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                
            if response.status_code == 200:
                logger.info(f"✅ Meta WhatsApp Template sent to {staff_whatsapp} for {request_id}")
                return True
            else:
                logger.error(f"⚠️ Meta API Error ({response.status_code}): {response.text}")
                # Don't return False yet, fall through to Twilio fallback
        except Exception as e:
            logger.error(f"⚠️ Meta WhatsApp send failed for {request_id}: {e}")
            # Fall through

        # 2. FALLBACK TO TWILIO (Standard Text via Sandbox)
        try:
            logger.info(f"🔄 Attempting Twilio Fallback for {request_id}...")
            
            staff_whatsapp = settings.SARANDA_STAFF_WHATSAPP
            if not staff_whatsapp.startswith("+"):
                staff_whatsapp = f"+61{staff_whatsapp.lstrip('0')}"
            
            emoji_map = {"order": "🧾", "change": "🔄", "cancel": "❌", "reservation": "📅"}
            emoji = emoji_map.get(request_type, "🧾")
            
            amount_line = f"\nTotal: ${total_amount:.2f}" if total_amount > 0 else ""
            message_body = f"""{emoji} {request_type.upper()} #{request_id}
━━━━━━━━━━━━━━━━
Customer: {customer_name}
Items: {order_summary}{amount_line}
Pickup: {pickup_time}

━━━━━━━━━━━━━━━━
Reply with:
✅ YES
❌ NO
⏳ LATE"""

            # ASYNC TWILIO CALL via httpx
            auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
            data = {
                "To": f"whatsapp:{staff_whatsapp}",
                "From": f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}",
                "Body": message_body
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data, auth=auth)
                response.raise_for_status()
                msg_data = response.json()
            
            logger.info(f"✅ Twilio Fallback sent to {staff_whatsapp} (SID: {msg_data.get('sid')})")
            return True
        except Exception as e:
            logger.error(f"❌ Critical: All WhatsApp delivery methods failed for {request_id}: {e}")
            return False
    

    async def send_customer_order_confirmation(
        self,
        customer_phone: str,
        order_id: str,
        status: str,  # "approved", "rejected", "too_late"
        pickup_time: str = None,
        message_override: str = None,
        tenant_id: str = "saranda" 
    ) -> bool:
        """
        Send confirmation/rejection to customer via SMS.
        Delegate to generic SMS service for dynamic sender ID handling.
        """
        from services.sms import sms_service
        
        try:
            # Build message based on status
            if message_override:
                message = message_override
            elif status == "approved":
                message = f"✅ Your Saranda order #{order_id} is confirmed! Ready for pickup in {pickup_time or '15-20 mins'}. Pay when you collect. See you soon!"
            elif status == "too_late":
                message = f"⏳ Sorry, the kitchen has already started your original order, so we couldn't make changes. Your order #{order_id} is still on track!"
            else:  # rejected
                message = f"Sorry, we couldn't process your order #{order_id} right now. Please call us or order via Uber Eats/DoorDash. Apologies for the inconvenience!"
            
            # Ensure proper phone format (E.164, no spaces/dashes)
            if not customer_phone:
                logger.warning(f"Aborting SMS: No phone number provided for order #{order_id}")
                return False
                
            clean_phone = re.sub(r'[^\d+]', '', customer_phone)
            if not clean_phone.startswith("+"):
                clean_phone = f"+61{clean_phone.lstrip('0')}"
            
            # Send via main SMS service (uses DB config for 'From' number)
            return await sms_service.send_sms(clean_phone, message, tenant_id=tenant_id)
            
        except Exception as e:
            logger.error(f"❌ Customer SMS exception for {order_id}: {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Customer SMS exception for {order_id}: {e}")
            return False
    async def notify_smart_transfer(
        self,
        customer_phone: str,
        summary: str,
        reason: str = "Time Limit Reached",
        tenant_id: str = "saranda"
    ) -> bool:
        """
        Notify staff of an incoming smart transfer.
        Sends a concisely summarized context via SMS so they know what the call is about.
        """
        from services.sms import sms_service
        
        try:
            # 1. Get staff phone for tenant (or default)
            # In a real app, we'd query DB configuration. For now, using config default.
            staff_phone = settings.SARANDA_STAFF_PHONE if tenant_id == "saranda" else settings.STAFF_PHONE_NUMBER
            
            # Ensure staff phone is cleaned
            clean_staff_phone = re.sub(r'[^\d+]', '', staff_phone)
            if not clean_staff_phone.startswith("+"):
                clean_staff_phone = f"+61{clean_staff_phone.lstrip('0')}"
            
            # 2. Build concise message
            # Limit length to ensure quick delivery and readability
            short_reason = reason.upper()
            
            message = f"🚀 INCOMING TRANSFER ({short_reason})\n\n"
            message += f"📞 Customer: {customer_phone}\n"
            message += f"📝 Context: {summary}\n\n"
            message += "Connecting now..."
            
            logger.info(f"📤 Sending Smart Transfer context to {clean_staff_phone}")
            
            # 3. Send SMS
            return await sms_service.send_sms(clean_staff_phone, message, tenant_id=tenant_id)
            
        except Exception as e:
            logger.error(f"❌ Smart Transfer Notification failed: {e}")
            return False

staff_notification_service = StaffNotificationService()
