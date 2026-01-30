
"""
Square Polling Job for Saranda
==============================
Polls Square API for status changes on pending orders and sends
SMS notifications to customers when their order is approved/rejected.
"""

import logging
from services.tenants.saranda.square_flows import saranda_approval_tracker, ApprovalState
from services.staff_notifications import staff_notification_service
from services.sms import sms_service
from services.appwrite import db_service
from datetime import datetime

logger = logging.getLogger(__name__)

async def square_polling_job():
    """
    Poll Square for updates on pending orders.
    Triggered by scheduler (e.g. every 1 minute).
    """
    try:
        # 1. Discover any missed pending orders from API if tracker is empty
        # (Self-healing: if server restarted, we lose memory state, so we check API)
        if saranda_approval_tracker.pending_count == 0:
            await saranda_approval_tracker.discover_pending_orders()
        
        # 2. Poll for updates
        changed_requests = await saranda_approval_tracker.poll_for_updates()
        
        if not changed_requests:
            return

        logger.info(f"🔔 Found {len(changed_requests)} order updates via polling")
        
        # 3. Process notifications
        for req in changed_requests:
            try:
                # Map state to notification type
                status_map = {
                    ApprovalState.APPROVED: "approved",
                    ApprovalState.REJECTED: "rejected",
                    ApprovalState.EXPIRED: "expired",
                    ApprovalState.MODIFIED: "modified"
                }
                
                status_label = status_map.get(req.state)
                
                if not status_label:
                    continue
                    
                # Prepare message override if needed
                msg_override = None
                if req.state == ApprovalState.APPROVED:
                    # Generic approved message
                    pass
                elif req.state == ApprovalState.REJECTED:
                    msg_override = f"Your order ({req.request_id}) could not be accepted by the kitchen at this time. Please call us."
                elif req.state == ApprovalState.EXPIRED:
                    msg_override = f"Sorry, we missed your order request ({req.request_id}). The team is very busy! Please call us directly."

                # === ROBUSTNESS: DUPLICATE CHECK ===
                # Check directly in DB if we already finalized this order/call
                # Support both Twilio SIDs (CA) and Simulator IDs (SIM)
                if req.call_id and (req.call_id.startswith("CA") or req.call_id.startswith("SIM")):
                    try:
                        # Fetch current log
                        collection_id = "call_transcripts_saranda" # Default for this job
                        queries = [db_service.Query.equal("call_sid", req.call_id)]
                        existing_logs = await db_service._make_request(
                            "GET", 
                            f"/databases/{db_service.motel_db_id}/collections/{collection_id}/documents", 
                            params={'queries': queries}
                        )
                        
                        if existing_logs and existing_logs.get("documents"):
                            log = existing_logs["documents"][0]
                            existing_sms = log.get("sms_status")
                            existing_outcome = log.get("outcome", "")
                            
                            # If we already sent an SMS, SKIP IT
                            if existing_sms in ["sent", "failed"]:
                                logger.info(f"🚫 Skipping duplicate notification for {req.request_id} (SMS already {existing_sms})")
                                continue
                                
                            # If outcome is already final (Approved/Rejected/Expired), SKIP IT
                            if "Order" in existing_outcome and existing_outcome != "Order Pending":
                                logger.info(f"🚫 Skipping duplicate notification for {req.request_id} (Outcome: {existing_outcome})")
                                continue
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to check duplicate status for {req.call_id}: {e}")

                # Send Customer SMS
                # Using staff_notification_service helper for consistency
                sms_sent = await staff_notification_service.send_customer_order_confirmation(
                    customer_phone=req.customer_phone,
                    order_id=req.request_id,
                    status=status_label,
                    pickup_time=req.pickup_time,
                    message_override=msg_override,
                    tenant_id="saranda"
                )
                
                # Update Call Log (if linked)
                if req.call_id and (req.call_id.startswith("CA") or req.call_id.startswith("SIM")): # Check if valid Twilio CallSid or Simulator
                    try:
                        updates = {
                            "sms_status": "sent" if sms_sent else "failed",
                            "outcome": f"Order {status_label.title()}",
                            "pms_reference": req.square_order_id, # Link Square Order ID
                            "sms_sent_at": datetime.now().isoformat()
                        }
                        await db_service.update_call_log_by_sid(tenant_id="saranda", call_sid=req.call_id, updates=updates)
                        logger.info(f"📝 Updated Call Log {req.call_id} with outcome: {updates['outcome']}")
                    except Exception as e:
                        logger.error(f"Failed to update call log: {e}")
                
                logger.info(f"✅ Notification sent for {req.request_id} ({status_label})")
                
            except Exception as e:
                logger.error(f"❌ Failed to notify for {req.request_id}: {e}")

    except Exception as e:
        logger.error(f"Error in square polling job: {e}")

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(square_polling_job())
