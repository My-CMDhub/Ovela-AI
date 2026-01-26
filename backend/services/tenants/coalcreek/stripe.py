"""
Coal Creek Motel - Stripe Payment Service
=========================================
Tenant-specific payment link generation and webhook handling.

Usage:
    from services.tenants.coalcreek.stripe import coalcreek_stripe_service
    result = await coalcreek_stripe_service.create_payment_link(...)
"""

import logging
import stripe
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from core.config import settings
from .config import COALCREEK_CONFIG

logger = logging.getLogger(__name__)
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")


class CoalCreekStripeService:
    """Stripe payment service for Coal Creek Motel."""
    
    def __init__(self):
        self.config = COALCREEK_CONFIG
        self.tenant_id = "coalcreek"
        self.configured = False
        
        # Configure Stripe if key available
        if hasattr(settings, 'STRIPE_SECRET_KEY') and settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            self.configured = True
        else:
            logger.warning("⚠️ Coal Creek Stripe not configured - STRIPE_SECRET_KEY missing")
    
    async def create_payment_link(
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
        """Create Stripe payment link for booking."""
        if not self.configured:
            return {"success": False, "error": "Stripe not configured"}
        
        try:
            total_cents = int(price_per_night * num_nights * 100)
            
            # Create product
            product = stripe.Product.create(
                name=f"Coal Creek Motel - {room_type}",
                description=f"{num_nights} night(s): {check_in} to {check_out}",
                metadata={
                    "tenant_id": self.tenant_id,
                    "booking_ref": booking_ref,
                    "customer_name": customer_name,
                    "room_type": room_type,
                }
            )
            
            # Create price
            price = stripe.Price.create(
                product=product.id,
                unit_amount=total_cents,
                currency="aud",
            )
            
            # Create payment link
            payment_link = stripe.PaymentLink.create(
                line_items=[{"price": price.id, "quantity": 1}],
                metadata={
                    "tenant_id": self.tenant_id,
                    "booking_ref": booking_ref,
                    "room_type": room_type,
                    "check_in": check_in,
                    "check_out": check_out,
                    "num_nights": str(num_nights),
                    "customer_email": customer_email,
                    "customer_name": customer_name,
                },
                after_completion={
                    "type": "hosted_confirmation",
                    "hosted_confirmation": {
                        "custom_message": f"Thank you! Your booking ({booking_ref}) is confirmed."
                    }
                },
                customer_creation="always",
                billing_address_collection="auto",
            )
            
            logger.info(f"✅ [Coal Creek] Payment link created: {booking_ref}")
            
            return {
                "success": True,
                "payment_url": payment_link.url,
                "payment_link_id": payment_link.id,
                "total_amount": price_per_night * num_nights
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ [Coal Creek] Stripe error: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"❌ [Coal Creek] Payment link error: {e}")
            return {"success": False, "error": "Payment system error"}
    
    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        """Verify Stripe webhook signature."""
        try:
            webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
            if not webhook_secret:
                return {"valid": False, "error": "Webhook secret not configured"}
            
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            return {"valid": True, "event": event}
            
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"❌ Invalid webhook signature: {e}")
            return {"valid": False, "error": "Invalid signature"}
    
    async def handle_payment_success(self, event_data: dict) -> dict:
        """
        Handle successful payment.
        
        Returns dict with booking info for status update.
        """
        try:
            metadata = event_data.get("metadata", {})
            
            # Only process Coal Creek payments
            if metadata.get("tenant_id") != self.tenant_id:
                return {"success": False, "error": "Wrong tenant"}
            
            booking_ref = metadata.get("booking_ref")
            customer_email = metadata.get("customer_email")
            customer_name = metadata.get("customer_name")
            
            if not booking_ref:
                return {"success": False, "error": "Missing booking_ref"}
            
            logger.info(f"✅ [Coal Creek] Payment confirmed: {booking_ref}")
            
            return {
                "success": True,
                "booking_ref": booking_ref,
                "customer_email": customer_email,
                "customer_name": customer_name,
                "room_type": metadata.get("room_type"),
                "check_in": metadata.get("check_in"),
                "check_out": metadata.get("check_out"),
                "num_nights": int(metadata.get("num_nights", 1))
            }
            
        except Exception as e:
            logger.error(f"❌ [Coal Creek] Payment handling error: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
coalcreek_stripe_service = CoalCreekStripeService()
