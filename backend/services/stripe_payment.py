"""
⚠️ DEPRECATED - Use Tenant-Specific Stripe Service Instead
===========================================================

This file is deprecated as of the multi-tenant restructure.

For Coal Creek Motel payment processing, use:
    from services.tenants.coalcreek.stripe import CoalCreekStripeService

For new tenants, create a tenant-specific Stripe service in:
    services/tenants/{tenant_name}/stripe.py

This file is kept for backward compatibility only.
===========================================================
"""

"""
Stripe Payment Service for Coal Creek Motel (LEGACY)
Handles payment link generation and webhook processing
"""
import logging
import stripe
from core.config import settings

logger = logging.getLogger(__name__)

class StripePaymentService:
    def __init__(self):
        # Will be configured when client provides API keys
        if hasattr(settings, 'STRIPE_SECRET_KEY') and settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY
        else:
            logger.warning("⚠️ Stripe not configured - STRIPE_SECRET_KEY missing")
    
    async def create_booking_payment_link(
        self,
        booking_ref: str,
        room_type: str,
        num_nights: int,
        price_per_night: float,
        customer_email: str,
        customer_name: str,
        check_in: str,
        check_out: str
    ) -> dict:
        """
        Create Stripe payment link for Coal Creek booking.
        
        Returns:
            dict with 'success', 'payment_url', and optional 'error'
        """
        try:
            if not stripe.api_key:
                return {
                    "success": False,
                    "error": "Stripe not configured"
                }
            
            total_amount = int(price_per_night * num_nights * 100)  # Convert to cents
            
            # Create product for this booking
            product = stripe.Product.create(
                name=f"Coal Creek Motel - {room_type}",
                description=f"{num_nights} night(s): {check_in} to {check_out}",
                metadata={
                    "booking_ref": booking_ref,
                    "customer_name": customer_name,
                    "room_type": room_type,
                }
            )
            
            # Create price
            price = stripe.Price.create(
                product=product.id,
                unit_amount=total_amount,
                currency="aud",
            )
            
            # Create payment link
            payment_link = stripe.PaymentLink.create(
                line_items=[{"price": price.id, "quantity": 1}],
                metadata={
                    "booking_ref": booking_ref,
                    "room_type": room_type,
                    "check_in": check_in,
                    "check_out": check_out,
                    "num_nights": str(num_nights),
                },
                after_completion={
                    "type": "hosted_confirmation",
                    "hosted_confirmation": {
                        "custom_message": f"Thank you! Your booking ({booking_ref}) is confirmed. Check your email for details."
                    }
                },
                # Allow customer to update email if needed
                customer_creation="always",
                # Collect billing address for verification
                billing_address_collection="auto",
            )
            
            logger.info(f"✅ Stripe payment link created for booking {booking_ref}: {payment_link.url}")
            
            return {
                "success": True,
                "payment_url": payment_link.url,
                "payment_link_id": payment_link.id,
                "total_amount": price_per_night * num_nights
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe error for booking {booking_ref}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"❌ Unexpected error creating payment link: {e}")
            return {
                "success": False,
                "error": "Payment system error"
            }
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> dict:
        """
        Verify Stripe webhook signature.
        
        Returns:
            dict with 'valid' bool and optional 'event' or 'error'
        """
        try:
            webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
            if not webhook_secret:
                logger.error("⚠️ STRIPE_WEBHOOK_SECRET not configured")
                return {"valid": False, "error": "Webhook secret not configured"}
            
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            
            return {"valid": True, "event": event}
            
        except ValueError as e:
            logger.error(f"❌ Invalid webhook payload: {e}")
            return {"valid": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"❌ Invalid webhook signature: {e}")
            return {"valid": False, "error": "Invalid signature"}
    
    async def handle_payment_success(self, event_data: dict) -> bool:
        """
        Handle successful payment webhook.
        Triggers booking confirmation email to customer.
        
        Args:
            event_data: Stripe event data from webhook
            
        Returns:
            bool indicating if handling was successful
        """
        try:
            # Extract metadata from payment
            metadata = event_data.get("metadata", {})
            booking_ref = metadata.get("booking_ref")
            customer_email = metadata.get("customer_email")
            customer_name = metadata.get("customer_name")
            
            if not all([booking_ref, customer_email, customer_name]):
                logger.error(f"⚠️ Missing metadata in payment webhook: {metadata}")
                return False
            
            logger.info(f"✅ Payment confirmed for booking {booking_ref}")
            
            # TODO: Send confirmation email to customer
            # TODO: Update booking status in database
            # TODO: Notify staff that payment is complete
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error handling payment success: {e}")
            return False


# Singleton instance
stripe_payment_service = StripePaymentService()
