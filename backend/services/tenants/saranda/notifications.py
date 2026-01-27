"""
Customer Notifications for Saranda
===================================
SMS notifications for order confirmations and rejections.
Uses Twilio SMS (same as existing system).
"""

import logging
from typing import Optional

from services.tenants.saranda.config import get_config
from services.tenants.saranda.square_flows import SquareOrderRequest, ApprovalState

logger = logging.getLogger(__name__)


async def send_customer_notification(request: SquareOrderRequest) -> bool:
    """
    Send SMS notification to customer based on order state.
    
    Returns True if sent successfully.
    """
    config = get_config()
    
    if not config.enable_sms_confirmation:
        logger.info(f"SMS notifications disabled - skipping for {request.request_id}")
        return False
    
    # Determine message based on state
    if request.state == ApprovalState.APPROVED:
        message = config.sms_confirmation_template.format(
            name=request.customer_name.split()[0],  # First name only
            pickup_time=request.pickup_time,
        )
    elif request.state in (ApprovalState.REJECTED, ApprovalState.EXPIRED):
        message = config.sms_rejection_template.format(
            name=request.customer_name.split()[0],
            phone=config.business_phone or "the restaurant",
        )
    elif request.state == ApprovalState.MODIFIED:
        message = (
            f"Hi {request.customer_name.split()[0]}! Your order has been updated by staff. "
            f"Pickup in ~{request.pickup_time} at Saranda Pizza. 🍕"
        )
    else:
        logger.debug(f"No notification needed for state: {request.state}")
        return False
    
    # Send via Twilio
    try:
        success = await _send_sms(
            to_phone=request.customer_phone,
            message=message,
            order_id=request.request_id,
        )
        
        if success:
            logger.info(f"📱 SMS sent to {request.customer_phone} for order {request.request_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Failed to send SMS for order {request.request_id}: {e}")
        return False


async def _send_sms(
    to_phone: str,
    message: str,
    order_id: str,
) -> bool:
    """
    Send SMS via Twilio.
    
    Reuses existing Twilio integration from staff_notifications.
    """
    try:
        # Import existing Twilio service
        from services.staff_notifications import staff_notification_service
        
        # Use the existing Twilio client
        # The send_whatsapp_customer_confirmation can send SMS too
        await staff_notification_service.send_whatsapp_customer_confirmation(
            customer_phone=to_phone,
            order_id=order_id,
            status="approved",  # Not used for SMS template
            message_override=message,  # Use our custom message
        )
        return True
        
    except ImportError:
        logger.error("staff_notifications service not available")
        return False
    except Exception as e:
        logger.error(f"Twilio SMS failed: {e}")
        return False


async def send_order_created_acknowledgment(
    customer_phone: str,
    customer_name: str,
    request_id: str,
) -> bool:
    """
    Send immediate acknowledgment when order is created.
    
    This confirms to the customer that their order was received
    and is being reviewed by staff.
    """
    config = get_config()
    
    if not config.enable_sms_confirmation:
        return False
    
    message = (
        f"Thanks {customer_name.split()[0]}! We've received your order (#{request_id}). "
        f"Staff are reviewing it now - you'll get a confirmation shortly. 🍕"
    )
    
    return await _send_sms(
        to_phone=customer_phone,
        message=message,
        order_id=request_id,
    )
