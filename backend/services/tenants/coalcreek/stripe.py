"""
Coal Creek Motel - Stripe Payment Service
=========================================
Tenant-specific payment link generation and webhook handling.

Usage:
    from services.tenants.coalcreek.stripe import coalcreek_stripe_service
    result = await coalcreek_stripe_service.create_payment_link(...)
"""

import logging
import asyncio
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
        check_out: str,
        success_url: str = None,
        cancel_url: str = None
    ) -> dict:
        """
        Create Stripe Checkout Session (Payment Mode) for booking.
        Set to expire in 24 hours to enforce urgency.
        """
        if not self.configured:
            return {"success": False, "error": "Stripe not configured"}
        
        try:
            # round, not int: a per-night price derived from a total (e.g.
            # $244 / 7) multiplies back to 24399.999…, which int() cut to a cent short.
            total_cents = int(round(price_per_night * num_nights * 100))
            expiry_time = int(datetime.now().timestamp() + 86400) # 24 Hours from now
            
            # Create Coupon for Checkout Session (One-time, expires)
            # In a worker thread: the SDK is synchronous, and this runs on the
            # event loop every live call shares (staff approve/regenerate).
            session = await asyncio.to_thread(
                stripe.checkout.Session.create,
                mode="payment",
                currency="aud",
                customer_email=customer_email,
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "aud",
                        "product_data": {
                            "name": f"Coal Creek Motel - {room_type}",
                            "description": f"{num_nights} night(s): {check_in} to {check_out}",
                            "metadata": {
                                "booking_ref": booking_ref
                            }
                        },
                        "unit_amount": total_cents,
                    },
                    "quantity": 1,
                }],
                metadata={
                    "tenant_id": self.tenant_id,
                    "booking_ref": booking_ref,
                    "customer_name": customer_name,
                    "room_type": room_type,
                    "check_in": check_in,
                    "check_out": check_out,
                    "num_nights": str(num_nights),
                    "type": "payment"
                },
                expires_at=expiry_time,
                success_url=success_url or f"{settings.BACKEND_URL}/payment-success?ref={booking_ref}",
                cancel_url=cancel_url or f"{settings.BACKEND_URL}/payment-cancel?ref={booking_ref}",
            )
            
            logger.info(f"✅ [Coal Creek] Payment session created: {booking_ref} (Expires in 24h)")
            
            return {
                "success": True,
                "payment_url": session.url,
                "session_id": session.id,
                "total_amount": price_per_night * num_nights
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ [Coal Creek] Stripe error: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"❌ [Coal Creek] Payment link error: {e}")
            return {"success": False, "error": "Payment system error"}
    
    async def create_setup_session(
        self,
        booking_ref: str,
        customer_email: str,
        customer_name: str,
        room_type: str,
        check_in: str,
        check_out: str,
        num_nights: int,
        # Read below but never declared, so every call raised NameError and the
        # card-on-file flow could not work at all.
        success_url: str = None,
        cancel_url: str = None
    ) -> dict:
        """
        Create a Setup Session to safely store card details without charging.
        (Pre-Auth / Card on File)
        """
        if not self.configured:
            return {"success": False, "error": "Stripe not configured"}
            
        try:
            session = await asyncio.to_thread(
                stripe.checkout.Session.create,
                mode="setup",
                currency="aud",
                customer_email=customer_email,
                payment_method_types=["card"],
                metadata={
                    "tenant_id": self.tenant_id,
                    "booking_ref": booking_ref,
                    "customer_name": customer_name,
                    "room_type": room_type,
                    "check_in": check_in,
                    "check_out": check_out,
                    "num_nights": str(num_nights),
                    "type": "setup" # Flag to identify setup vs payment
                },
                success_url=success_url or "https://coalcreekmotel.com.au/booking/success?ref=" + booking_ref, 
                cancel_url=cancel_url or "https://coalcreekmotel.com.au/booking/cancel?ref=" + booking_ref,
            )
            
            logger.info(f"✅ [Coal Creek] Setup session created: {booking_ref}")
            
            return {
                "success": True,
                "payment_url": session.url,
                "session_id": session.id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ [Coal Creek] Stripe setup error: {e}")
            return {"success": False, "error": str(e)}
            
    async def expire_checkout_from_url(self, url: str) -> bool:
        """
        Expire the Checkout Session behind a payment link, so it can no longer
        be paid. The session id is not stored on bookings, but the link carries
        it (checkout.stripe.com/c/pay/cs_...). Best effort: False when there is
        no id, Stripe is not configured, or Stripe refuses (already paid or
        expired sessions cannot be expired).
        """
        import re as _re
        m = _re.search(r"(cs_(?:test|live)_[A-Za-z0-9]+)", url or "")
        if not (self.configured and m):
            return False
        try:
            await asyncio.to_thread(stripe.checkout.Session.expire, m.group(1))
            logger.info("[Coal Creek] Expired superseded checkout %s…", m.group(1)[:16])
            return True
        except Exception as e:
            logger.warning("[Coal Creek] Could not expire checkout %s…: %s", m.group(1)[:16], e)
            return False

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
    
    async def handle_checkout_completion(self, session: dict) -> dict:
        """
        Handle checkout.session.completed (for both Payment and Setup).
        Returns dict with details and 'type' ('payment' or 'setup').
        """
        try:
            if not isinstance(session, dict):
                mode = getattr(session, "mode", None)
                metadata_obj = getattr(session, "metadata", {})
                metadata = metadata_obj if isinstance(metadata_obj, dict) else (metadata_obj.to_dict() if hasattr(metadata_obj, "to_dict") else dict(metadata_obj))
                customer_email = getattr(session, "customer_email", None)
                setup_intent = getattr(session, "setup_intent", None)
                payment_intent = getattr(session, "payment_intent", None)
                amount_total = getattr(session, "amount_total", None)
            else:
                metadata = session.get("metadata", {})
                mode = session.get("mode")
                customer_details = session.get("customer_details") or {}
                customer_email = session.get("customer_email") or customer_details.get("email")
                setup_intent = session.get("setup_intent")
                payment_intent = session.get("payment_intent")
                amount_total = session.get("amount_total")
            
            # Only process Coal Creek
            if metadata.get("tenant_id") != self.tenant_id:
                return {"success": False, "error": "Wrong tenant"}
            
            booking_ref = metadata.get("booking_ref")
            if not booking_ref:
                return {"success": False, "error": "Missing booking_ref"}
            
            logger.info(f"✅ [Coal Creek] Checkout completed: {booking_ref} (Mode: {mode})")
            
            result = {
                "success": True,
                "booking_ref": booking_ref,
                "customer_email": customer_email or metadata.get("customer_email"),
                "customer_name": metadata.get("customer_name"),
                "room_type": metadata.get("room_type"),
                "check_in": metadata.get("check_in"),
                "check_out": metadata.get("check_out"),
                "num_nights": int(metadata.get("num_nights", 1)),
                "mode": mode
            }

            if mode == "setup":
                result["setup_intent"] = setup_intent
                result["type"] = "setup"
            else:
                result["payment_intent"] = payment_intent
                result["amount_total"] = amount_total
                result["type"] = "payment"
                
            return result
            
        except Exception as e:
            logger.error(f"❌ [Coal Creek] Payment handling error: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
coalcreek_stripe_service = CoalCreekStripeService()
