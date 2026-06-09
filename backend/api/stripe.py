"""
Stripe Webhook API Endpoint — POST /api/stripe/webhook
Handles payment confirmation webhooks from Stripe.

P11-E AUDIT NOTE (2026-06-03):
  Two webhook endpoints exist in this codebase:
    1. POST /api/stripe/webhook          (this file)
    2. POST /api/motel/payments/webhook  (api/dashboard.py:864)

  Only ONE URL can be registered in the Stripe dashboard at a time.
  api/dashboard.py handler is MORE COMPLETE: handles checkout.session.expired,
  setup mode vs payment mode, and uses doc.get("num_nights", 1) from Appwrite.
  This handler (api/stripe.py) is simpler but now also has correct num_nights
  derivation. Both are kept live. Check Stripe dashboard to confirm which URL
  is registered. If switching to the dashboard handler, comment out this route.
"""

import logging
from fastapi import APIRouter, Request, HTTPException
from services.stripe_payment import stripe_payment_service
from services.email import email_service
from services.appwrite import db_service
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.
    
    Events we care about:
    - checkout.session.completed: Payment link completed
    - payment_intent.succeeded: Payment successful
    """
    try:
        # Get raw body and signature
        payload = await request.body()
        signature = request.headers.get("stripe-signature")
        
        if not signature:
            logger.error("⚠️ Missing Stripe signature header")
            raise HTTPException(status_code=400, detail="Missing signature")
        
        # Verify webhook signature
        verification = stripe_payment_service.verify_webhook_signature(payload, signature)
        
        if not verification.get("valid"):
            logger.error(f"❌ Invalid webhook signature: {verification.get('error')}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        event = verification.get("event")
        event_type = event.get("type")
        
        logger.info(f"📨 Stripe webhook received: {event_type}")
        
        # Handle payment success
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]

            # Extract metadata (all fields set by create_checkout_session)
            metadata = session.get("metadata", {})
            booking_ref = metadata.get("booking_ref", "")
            guest_email = metadata.get("guest_email", "")
            guest_name = metadata.get("guest_name", "Guest")
            room_type = metadata.get("room_type", "Queen Room")
            check_in = metadata.get("check_in", "")
            check_out = metadata.get("check_out", "")

            # Get payment amount
            amount_total = session.get("amount_total", 0) / 100  # Convert cents to dollars
            stripe_payment_id = session.get("payment_intent")

            # Derive num_nights from metadata (P11-A fix: was hardcoded to 1)
            try:
                from datetime import datetime as _dt
                _ci = _dt.strptime(check_in, "%Y-%m-%d").date()
                _co = _dt.strptime(check_out, "%Y-%m-%d").date()
                num_nights = max(1, (_co - _ci).days)
            except Exception:
                num_nights = 1
                logger.warning("Could not derive num_nights from metadata (%s → %s), defaulting to 1", check_in, check_out)

            logger.info(f"✅ Payment confirmed for booking {booking_ref}: ${amount_total} ({num_nights} nights)")
            logger.info(f"📧 Guest email: {guest_email}, Name: {guest_name}")

            stripe_session_id = session.get("id", "")  # I3/C3: capture Stripe session ID for fallback lookup

            # Update booking status in Appwrite motel_reservations
            # I3/C3: DB failure is isolated — never kills the email send below
            booking_doc_id = None
            if booking_ref:
                try:
                    # Primary: query by booking_ref (written in Stripe metadata at checkout creation)
                    booking_doc = await db_service.get_booking_by_reference(booking_ref)
                    if not booking_doc and stripe_session_id:
                        # C3 Fallback: query by stripe_session_id field if ref lookup misses
                        logger.warning("⚠️ I3: booking_ref lookup missed — falling back to stripe_session_id query")
                        booking_doc = await db_service.get_booking_by_stripe_session(stripe_session_id)
                    if booking_doc and booking_doc.get("$id"):
                        booking_doc_id = booking_doc["$id"]
                        await db_service.update_booking_payment_status(
                            booking_id=booking_doc_id,
                            payment_status="paid",
                            stripe_payment_id=stripe_payment_id,
                            deposit_paid=amount_total,
                        )
                        logger.info(f"✅ Booking {booking_ref} marked as paid in Appwrite")
                    else:
                        logger.error(f"❌ I3: Could not find booking doc for ref={booking_ref} / session={stripe_session_id}")
                except Exception as e:
                    logger.warning(f"⚠️ I3: DB update failed (non-fatal, email will still send): {e}")
            else:
                logger.error("❌ I3: Stripe webhook missing booking_ref in metadata — cannot update DB")

            # Send confirmation email to guest (via Gmail / Coal Creek SMTP)
            # C3: Fully isolated — DB failure above CANNOT prevent this from running
            if guest_email:
                try:
                    await email_service.send_guest_booking_confirmation(
                        guest_email=guest_email,
                        guest_name=guest_name,
                        booking_reference=booking_ref,
                        room_type=room_type,
                        check_in=check_in,
                        check_out=check_out,
                        num_nights=num_nights,
                        total_amount=amount_total,
                        business_name="Coal Creek Motel",
                        tenant_id="coalcreek"
                    )
                    logger.info(f"📧 Confirmation email sent to {guest_email}")
                except Exception as e:
                    logger.error(f"❌ I3: Failed to send confirmation email: {e}")

            # Notify staff via Ovela SMTP (notifications@ovela.dev)
            try:
                staff_email = settings.STAFF_NOTIFICATION_RECIPIENTS or "officialcoalcreek@gmail.com"
                await email_service.send_staff_payment_notification(
                    staff_email=staff_email,
                    booking_reference=booking_ref,
                    customer_name=guest_name,
                    customer_email=guest_email,
                    room_type=room_type,
                    check_in=check_in,
                    check_out=check_out,
                    num_nights=num_nights,
                    amount_paid=amount_total
                )
                logger.info(f"📧 Staff payment notification sent to {staff_email}")
            except Exception as e:
                logger.error(f"❌ Failed to send staff notification: {e}")

            return {"status": "success", "message": "Payment processed"}
        
        # Handle other events
        elif event_type == "payment_intent.succeeded":
            logger.info("💰 Payment intent succeeded")
            return {"status": "success", "message": "Payment intent noted"}
        
        else:
            logger.info(f"ℹ️ Unhandled event type: {event_type}")
            return {"status": "success", "message": "Event received"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")
