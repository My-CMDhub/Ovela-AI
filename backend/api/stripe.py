"""
Stripe Webhook API Endpoint
Handles payment confirmation webhooks from Stripe
"""
import logging
from fastapi import APIRouter, Request, HTTPException
from services.stripe_payment import stripe_payment_service
from services.email import email_service
from services.appwrite import db_service
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/stripe/webhook")
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

            logger.info(f"✅ Payment confirmed for booking {booking_ref}: ${amount_total}")
            logger.info(f"📧 Guest email: {guest_email}, Name: {guest_name}")

            # Update booking status in Appwrite motel_reservations
            if booking_ref:
                try:
                    # Get booking doc by reference
                    booking_doc = await db_service.get_booking_by_reference(booking_ref)
                    if booking_doc and booking_doc.get("$id"):
                        await db_service.update_booking_payment_status(
                            booking_id=booking_doc["$id"],
                            payment_status="paid",
                            stripe_payment_id=stripe_payment_id,
                        )
                        logger.info(f"� Booking {booking_ref} marked as paid in Appwrite")
                except Exception as e:
                    logger.warning(f"Could not update DB status: {e}")

            # Send confirmation email to guest (via Gmail / Coal Creek SMTP)
            if guest_email:
                try:
                    await email_service.send_guest_booking_confirmation(
                        guest_email=guest_email,
                        guest_name=guest_name,
                        booking_reference=booking_ref,
                        room_type=room_type,
                        check_in=check_in,
                        check_out=check_out,
                        num_nights=1,
                        total_amount=amount_total,
                        business_name="Coal Creek Motel",
                        tenant_id="coalcreek"
                    )
                    logger.info(f"📧 Confirmation email sent to {guest_email}")
                except Exception as e:
                    logger.error(f"❌ Failed to send confirmation email: {e}")

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
                    num_nights=1,
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
