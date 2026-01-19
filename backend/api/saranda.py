"""
Saranda Restaurant Webhooks
===========================
Webhook endpoints for Saranda Cafe & Pizzeria HITL system.
Handles incoming WhatsApp replies from staff for order approvals.
"""
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import Response
import logging

from services.saranda_flows import (
    saranda_queue,
    parse_staff_reply,
    RequestType,
    RequestStatus,
)
from services.staff_notifications import staff_notification_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/whatsapp-reply")
async def handle_whatsapp_reply(
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(default="")
):
    """
    Receive staff WhatsApp replies from Twilio webhook.
    
    Staff can reply with:
    - YES / yep / confirm / approve / ✅ → Approve order
    - NO / nope / reject / ❌ → Reject order (with optional reason codes 1/2/3)
    - LATE / too late / already started / ⏳ → Kitchen already started
    
    Flow:
    1. Parse the message using flexible matching
    2. Find the active request in queue
    3. Resolve with staff decision
    4. Send SMS confirmation to customer
    5. Activate next queued request if any
    """
    logger.info(f"📱 WhatsApp reply from {From}: '{Body}' (SID: {MessageSid})")
    
    # DEFENSIVE LAYER: Only process if there's an active request
    # This prevents false positives from group chat noise
    active_request = saranda_queue.get_active()
    
    if active_request is None:
        # No active request - ignore ALL messages (even if they look like commands)
        # This handles group chat scenarios where staff might say "yes" or "no" casually
        logger.info(f"⚠️ No active request in queue - ignoring message from {From}")
        return Response(content="", media_type="text/plain")
    
    # Now parse the reply (we know there's something to respond to)
    command, reason = parse_staff_reply(Body)
    
    if command is None:
        # Unrecognized reply - log but don't respond (per design)
        logger.info(f"⚠️ Unrecognized reply from {From}: '{Body}' - ignoring")
        return Response(content="", media_type="text/plain")
    
    # Get request details
    request_id = active_request.id
    customer_phone = active_request.customer_phone
    
    # Determine pickup time for confirmation message
    pickup_time = None
    if hasattr(active_request, 'pickup_time'):
        pickup_time = active_request.pickup_time
    elif hasattr(active_request, 'time'):
        # Reservation
        pickup_time = f"{active_request.date} at {active_request.time}"
    
    # Check if expired before resolving
    if active_request.is_expired:
        logger.warning(f"⚠️ Request {request_id} has expired - ignoring late reply")
        # Expire it and move to next
        saranda_queue.expire_stale()
        return Response(content="", media_type="text/plain")
    
    # Resolve the request
    resolved = saranda_queue.resolve(request_id, command, reason)
    
    if not resolved:
        logger.error(f"❌ Failed to resolve request {request_id}")
        return Response(content="", media_type="text/plain")
    
    logger.info(f"✅ Request {request_id} resolved: {command}")
    
    # Map command to status for customer notification
    status_map = {
        "YES": "approved",
        "NO": "rejected", 
        "LATE": "too_late"
    }
    status = status_map.get(command, "rejected")
    
    # Send SMS confirmation to customer
    try:
        await staff_notification_service.send_whatsapp_customer_confirmation(
            customer_phone=customer_phone,
            order_id=request_id,
            status=status,
            pickup_time=pickup_time
        )
        logger.info(f"📤 Customer SMS sent to {customer_phone} for {request_id}")
    except Exception as e:
        logger.error(f"❌ Failed to send customer SMS: {e}")
        # Don't fail the webhook - staff decision was still recorded
    
    # Check if there's a next request that needs WhatsApp notification
    next_request = saranda_queue.get_active()
    if next_request:
        # Send WhatsApp notification for the next order
        try:
            # Determine request type label
            type_label = "order"
            if hasattr(next_request, 'request_type'):
                type_label = next_request.request_type.value
            
            # Get order summary
            order_summary = next_request.format_for_whatsapp()
            
            # Determine pickup time for next request
            next_pickup = None
            total_amount = 0.0
            if hasattr(next_request, 'pickup_time'):
                next_pickup = next_request.pickup_time
                total_amount = next_request.total_amount
            elif hasattr(next_request, 'time'):
                next_pickup = f"{next_request.date} at {next_request.time}"
            
            await staff_notification_service.send_whatsapp_order_approval(
                request_id=next_request.id,
                request_type=type_label,
                customer_name=next_request.customer_name,
                order_summary=order_summary,
                pickup_time=next_pickup or "ASAP",
                total_amount=total_amount
            )
            logger.info(f"📱 Next request {next_request.id} sent to staff for approval")
        except Exception as e:
            logger.error(f"❌ Failed to send WhatsApp for next request: {e}")
    
    # Return empty response (Twilio expects 200 OK)
    return Response(content="", media_type="text/plain")


@router.get("/queue-status")
async def get_queue_status():
    """
    Get current queue status for debugging/monitoring.
    """
    active = saranda_queue.get_active()
    
    return {
        "active_request": {
            "id": active.id if active else None,
            "status": active.status.value if active else None,
            "customer_name": active.customer_name if active else None,
            "time_remaining_seconds": active.time_remaining_seconds if active else None,
        } if active else None,
        "queue_length": saranda_queue.queue_length,
        "is_busy": saranda_queue.is_busy
    }
