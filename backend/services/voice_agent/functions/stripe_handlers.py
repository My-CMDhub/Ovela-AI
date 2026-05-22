"""
Stripe Automated Payment Handler — Ovela AI Hospitality.

Generates one-time Stripe Checkout sessions for motel bookings,
surfacing a payment link that can be SMS'd or emailed to the guest
immediately after a booking is confirmed over the phone.

Hot-path contract:
  - create_checkout_session() NEVER raises — returns None on any Stripe error.
  - All errors are logged but never re-raised into the voice agent handler.

Stripe SDK note:
  STRIPE_SECRET_KEY is set via settings.STRIPE_SECRET_KEY (Optional).
  If not configured, create_checkout_session() returns None gracefully.
"""

import logging
from typing import Optional

import stripe

from core.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Stripe initialisation
# The key is set lazily so tests can patch it without triggering import errors.
# ─────────────────────────────────────────────────────────────────────────────

_STRIPE_CONFIGURED = bool(settings.STRIPE_SECRET_KEY)
if _STRIPE_CONFIGURED:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(
    amount_aud: int,
    room_type: str,
    booking_ref: Optional[str] = None,
    success_url: str = "https://ovela.dev/payment-success",
    cancel_url: str = "https://ovela.dev/payment-cancel",
) -> Optional[str]:
    """
    Create a Stripe Checkout Session for a motel room booking.

    Returns the hosted checkout URL as a string so it can be sent to the
    guest via SMS or email immediately after the booking call.

    Never raises — returns None on any Stripe API error.

    Args:
        amount_aud:   Booking amount in AUD dollars (e.g. 150 for $150).
        room_type:    Room type string for the product name (e.g. "queen").
        booking_ref:  Optional booking reference to attach as Stripe metadata.
        success_url:  URL Stripe redirects to on successful payment.
        cancel_url:   URL Stripe redirects to if user cancels checkout.

    Returns:
        Stripe hosted checkout URL (str) or None on failure.
    """
    if not _STRIPE_CONFIGURED:
        logger.warning("💳 Stripe not configured (STRIPE_SECRET_KEY missing) — skipping checkout creation")
        return None

    try:
        product_name = f"Coal Creek Motel — {room_type.capitalize()} Room"
        amount_cents = amount_aud * 100  # Stripe requires integer cents

        metadata = {}
        if booking_ref:
            metadata["booking_ref"] = booking_ref

        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "aud",
                        "product_data": {
                            "name": product_name,
                            "description": f"One night at Coal Creek Motel — {room_type.capitalize()} Room",
                        },
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )

        logger.info(
            "💳 Stripe checkout session created | ref=%s | amount=AUD$%d | room=%s",
            booking_ref or "N/A",
            amount_aud,
            room_type,
        )
        return session.url

    except Exception as exc:
        logger.error(
            "💳 Stripe checkout creation failed | ref=%s | amount=AUD$%d — %s",
            booking_ref or "N/A",
            amount_aud,
            exc,
        )
        return None
