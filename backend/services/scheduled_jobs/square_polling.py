
"""
Square Polling Job for Saranda
==============================
Polls Square API for status changes on pending orders and sends
SMS notifications to customers when their order is approved/rejected.
"""

import logging
import json
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
            discovered = await saranda_approval_tracker.discover_pending_orders()
            
            # --- HARDENING: SYNC WITH DB ---
            # Remove any discovered orders that are already finalized in our DB
            # This prevents "zombie" notifications on server restart
            if discovered:
                logger.info(f"🛡️ Validating {len(discovered)} discovered orders against DB...")
                to_remove = []
                for req in discovered:
                    try:
                        if not req.call_id: continue
                        
                        collection_id = "call_transcripts_saranda"
                        queries = [db_service.Query.equal("call_sid", req.call_id)]
                        
                        # We use the internal request helper to avoid full dependency if possible, 
                        # or just use standard db_service method if exposed.
                        # Using raw request for speed/safety matching existing pattern
                        existing = await db_service._make_request(
                            "GET", 
                            f"/databases/{db_service.motel_db_id}/collections/{collection_id}/documents", 
                            params={'queries': queries}
                        )
                        
                        if existing and existing.get("documents"):
                            doc = existing["documents"][0]
                            outcome = doc.get("outcome", "")
                            # If outcome suggests final state, remove from tracking
                            if "Order" in outcome and outcome != "Order Pending":
                                logger.info(f"🚫 Ignoring already finalized order {req.request_id} (Outcome: {outcome})")
                                to_remove.append(req.square_order_id)
                    except Exception as e:
                        logger.warning(f"Failed to validate {req.request_id} against DB: {e}")
                
                # Remove from tracker
                for oid in to_remove:
                    if oid in saranda_approval_tracker._pending:
                        # Move to resolved silently
                        req = saranda_approval_tracker._pending.pop(oid)
                        saranda_approval_tracker._resolved[oid] = req
                        req.state = ApprovalState.APPROVED # Mark as 'done' so we don't track
            # -------------------------------
        
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

                # === ROBUSTNESS: DUPLICATE CHECK & LOCK ===
                # 1. Check/Lock DB before sending anything
                # If we have a call_id, verify we haven't already processed this outcome
                if req.call_id and (req.call_id.startswith("CA") or req.call_id.startswith("SIM")):
                    try:
                        # Try to get existing log
                        collection_id = "call_transcripts_saranda"
                        queries = [db_service.Query.equal("call_sid", req.call_id)]
                        existing_logs = await db_service._make_request(
                            "GET", 
                            f"/databases/{db_service.motel_db_id}/collections/{collection_id}/documents", 
                            params={'queries': queries}
                        )
                        
                        doc_id = None
                        if existing_logs and existing_logs.get("documents"):
                            log = existing_logs["documents"][0]
                            doc_id = log.get("$id")
                            existing_outcome = log.get("outcome", "")
                            
                            # If already finalized or processing with SAME status, SKIP
                            # e.g. "Order Approved" -> don't send again
                            if status_label.title() in existing_outcome:
                                logger.info(f"🚫 Skipping duplicate notification for {req.request_id} (Already {existing_outcome})")
                                continue
                                
                            # If outcome suggests final state (and different?), usually we respect the first final state
                            if "Order" in existing_outcome and existing_outcome != "Order Pending":
                                logger.info(f"🚫 Skipping duplicate notification for {req.request_id} (Outcome: {existing_outcome})")
                                continue
                        else:
                            # If not found (Likely SIM order not yet logged), create it immediately as "Processing" to lock it
                            # If this fails with 409, it means another thread beat us to it -> SKIP
                            try:
                                result = await db_service.save_call_transcript(
                                     tenant_id="saranda",
                                     call_sid=req.call_id,
                                     caller_phone=req.customer_phone,
                                     transcript=json.dumps([{"role": "system", "content": f"Simulator Order: {req.items_summary}"}]),
                                     duration=0,
                                     status=f"Order {status_label.title()}", # Lock state immediately
                                     booking_ref=req.square_order_id,
                                     customer_name=req.customer_name or "Simulator User",
                                     call_summary=f"Simulated Order {status_label}",
                                     metadata={"sms_status": "sending"}
                                )
                                if result:
                                    doc_id = result.get("$id")
                                else:
                                    # Failed to create but no exception? treat as fail
                                    continue
                            except Exception as e:
                                logger.warning(f"🔒 Race condition detected for {req.call_id} (Create failed): {e}")
                                continue

                    except Exception as e:
                        logger.warning(f"⚠️ Failed duplicate check for {req.call_id}: {e}")
                        # Proceed cautiously or skip? 
                        # If DB is down, we risk spamming. Better to skip.
                        pass

                # 2. Send Customer SMS
                sms_sent = await staff_notification_service.send_customer_order_confirmation(
                    customer_phone=req.customer_phone,
                    order_id=req.request_id,
                    status=status_label,
                    pickup_time=req.pickup_time,
                    customer_name=req.customer_name,
                    items_summary=req.items_summary,
                    total_amount=req.total_dollars,
                    message_override=msg_override,
                    tenant_id="saranda"
                )
                
                # 3. Update Call Log to Final State
                if req.call_id and (req.call_id.startswith("CA") or req.call_id.startswith("SIM")): 
                    logger.info(f"🔄 Updating Call Log for SID: {req.call_id} -> {status_label}")
                    try:
                        updates = {
                            "sms_status": "sent" if sms_sent else "failed",
                            "outcome": f"Order {status_label.title()}",
                            "pms_reference": req.square_order_id, 
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
