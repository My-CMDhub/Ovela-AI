"""
Stripe Webhook API Endpoint
Handles payment confirmation webhooks from Stripe
"""
import logging
from fastapi import APIRouter, Request, HTTPException
from services.stripe_payment import stripe_payment_service
from services.email import email_service
from services.appwrite import db_service

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
            
            # Get customer email from Stripe session (actual email they entered)
            customer_email = session.get("customer_details", {}).get("email") or session.get("customer_email")
            customer_name = session.get("customer_details", {}).get("name", "Guest")
            
            # Extract metadata
            metadata = session.get("metadata", {})
            booking_ref = metadata.get("booking_ref")
            room_type = metadata.get("room_type")
            check_in = metadata.get("check_in")
            check_out = metadata.get("check_out")
            num_nights = int(metadata.get("num_nights", 1))
            
            # Get payment amount
            amount_total = session.get("amount_total", 0) / 100  # Convert cents to dollars
            
            logger.info(f"✅ Payment confirmed for booking {booking_ref}: ${amount_total}")
            logger.info(f"📧 Customer email: {customer_email}, Name: {customer_name}")
            
            # Update booking status in database
            try:
                db_service.update_notification_status(
                    notification_id=booking_ref,
                    status="paid"
                )
            except Exception as e:
                logger.warning(f"Could not update DB status: {e}")
            
            # Send confirmation email to customer
            if customer_email:
                try:
                    await email_service.send_guest_booking_confirmation(
                        guest_email=customer_email,
                        guest_name=customer_name,
                        booking_reference=booking_ref,
                        room_type=room_type,
                        check_in=check_in,
                        check_out=check_out,
                        num_nights=num_nights,
                        total_amount=amount_total
                    )
                    logger.info(f"📧 Confirmation email sent to {customer_email}")
                except Exception as e:
                    logger.error(f"❌ Failed to send confirmation email: {e}")
            
            # Notify staff that payment is complete (industry best practice)
            try:
                # TODO: Get staff email from tenant config
                staff_email = "getnewone2022@gmail.com"  # Placeholder - update from tenant config
                
                await email_service.send_staff_payment_notification(
                    staff_email=staff_email,
                    booking_reference=booking_ref,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    room_type=room_type,
                    check_in=check_in,
                    check_out=check_out,
                    num_nights=num_nights,
                    amount_paid=amount_total
                )
                logger.info(f"📧 Staff payment notification sent to {staff_email}")
            except Exception as e:
                logger.error(f"❌ Failed to send staff notification: {e}")
            
            # TODO: Send SMS to customer with booking details
            
            
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
