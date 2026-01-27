"""
Square Webhook Handler for Saranda
===================================
FastAPI router for Square webhook callbacks.

Handles:
- order.updated: Detect staff approval/rejection
- Signature verification for security
"""

import hmac
import hashlib
import base64
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse

from services.tenants.saranda.config import get_config
from services.tenants.saranda.square_flows import (
    saranda_approval_tracker,
    ApprovalState,
)
from services.tenants.saranda.notifications import send_customer_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saranda", tags=["saranda"])


def verify_webhook_signature(
    body: bytes,
    signature: str,
    notification_url: str,
    signature_key: str,
) -> bool:
    """
    Verify Square webhook signature.
    
    Square uses HMAC-SHA256 with base64 encoding.
    The signature is computed over: notification_url + body
    """
    if not signature_key:
        logger.warning("No webhook signature key configured - skipping verification")
        return True  # Allow in development
    
    try:
        # Square concatenates URL + body for signature
        string_to_sign = notification_url + body.decode("utf-8")
        
        # Compute HMAC-SHA256
        hmac_obj = hmac.new(
            signature_key.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        )
        expected_signature = base64.b64encode(hmac_obj.digest()).decode("utf-8")
        
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


@router.post("/square/webhook")
async def handle_square_webhook(
    request: Request,
    x_square_hmacsha256_signature: Optional[str] = Header(None),
):
    """
    Receive Square webhook events.
    
    Events we care about:
    - order.created: Log for debugging (we created it)
    - order.updated: Detect staff approval/rejection
    """
    config = get_config()
    body = await request.body()
    
    # Verify signature in production
    if config.square_webhook_signature_key:
        notification_url = str(request.url)
        if not verify_webhook_signature(
            body=body,
            signature=x_square_hmacsha256_signature or "",
            notification_url=notification_url,
            signature_key=config.square_webhook_signature_key,
        ):
            logger.warning("Invalid webhook signature - rejecting")
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse event
    try:
        event = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    event_type = event.get("type", "")
    data = event.get("data", {})
    object_data = data.get("object", {})
    
    logger.info(f"📬 Square webhook: {event_type}")
    
    # Handle order events
    if event_type in ("order.created", "order.updated"):
        order_data = object_data.get("order", {})
        order_id = order_data.get("id")
        
        if not order_id:
            return JSONResponse({"status": "ok"})
        
        # Check if this is one of our AI-created orders
        reference_id = order_data.get("reference_id", "")
        if not reference_id.startswith("ovela:"):
            # Not our order - ignore
            logger.debug(f"Order {order_id} not AI-created - ignoring")
            return JSONResponse({"status": "ok"})
        
        if event_type == "order.updated":
            # Process potential approval/rejection
            changed_request = saranda_approval_tracker.process_webhook_event(
                order_id=order_id,
                event_type=event_type,
                order_data=order_data,
            )
            
            if changed_request:
                # Send customer notification based on state
                await send_customer_notification(changed_request)
    
    return JSONResponse({"status": "ok"})


@router.get("/square/status")
async def get_square_status():
    """
    Get current Square integration status for debugging.
    """
    from services.tenants.saranda.square_client import SquareClient
    
    client = SquareClient()
    connected = await client.test_connection()
    
    return {
        "connected": connected,
        "environment": get_config().square_environment,
        "pending_orders": saranda_approval_tracker.pending_count,
    }


@router.get("/pending-orders")
async def get_pending_orders():
    """
    List all pending orders awaiting staff approval.
    """
    pending = saranda_approval_tracker.get_pending()
    
    return {
        "count": len(pending),
        "orders": [
            {
                "request_id": req.request_id,
                "square_order_id": req.square_order_id,
                "customer_name": req.customer_name,
                "total": f"${req.total_dollars:.2f}",
                "pickup_time": req.pickup_time,
                "time_remaining_seconds": req.time_remaining_seconds,
                "created_at": req.created_at.isoformat(),
            }
            for req in pending
        ],
    }
