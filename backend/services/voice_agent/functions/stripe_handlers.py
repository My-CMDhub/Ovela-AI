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
import time
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
    guest_email: Optional[str] = None,
    guest_name: Optional[str] = None,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
    expires_at: Optional[int] = None,
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
        guest_email:  Optional guest email — stored in metadata for webhook.
        guest_name:   Optional guest name — stored in metadata for webhook.
        check_in:     Optional check-in date (YYYY-MM-DD) — stored in metadata.
        check_out:    Optional check-out date (YYYY-MM-DD) — stored in metadata.
        success_url:  Override URL Stripe redirects to on payment success.
        cancel_url:   Override URL Stripe redirects to if user cancels.
        expires_at:   Unix timestamp for session expiry; defaults to now+1800.

    Returns:
        Stripe hosted checkout URL (str) or None on failure.
    """
    if not _STRIPE_CONFIGURED:
        logger.warning("💳 Stripe not configured (STRIPE_SECRET_KEY missing) — skipping checkout creation")
        return None

    try:
        # Normalize room type formatting
        clean_room_type = room_type.title()
        if "Room" not in clean_room_type:
            clean_room_type = f"{clean_room_type} Room"

        product_name = f"Coal Creek Motel — {clean_room_type}"
        amount_cents = amount_aud * 100  # Stripe requires integer cents

        _success_url = success_url or f"{settings.BACKEND_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}"
        _cancel_url = cancel_url or f"{settings.BACKEND_URL}/payment-cancel"
        _expires_at = expires_at if expires_at else int(time.time()) + 1800

        metadata = {"room_type": room_type}
        if booking_ref:
            metadata["booking_ref"] = booking_ref
        if guest_email:
            metadata["guest_email"] = guest_email
        if guest_name:
            metadata["guest_name"] = guest_name
        if check_in:
            metadata["check_in"] = check_in
        if check_out:
            metadata["check_out"] = check_out

        # Dynamically build description based on check-in/out
        description = f"Stay at Coal Creek Motel — {clean_room_type}"
        if check_in and check_out:
            try:
                from datetime import datetime
                d1 = datetime.strptime(check_in, "%Y-%m-%d")
                d2 = datetime.strptime(check_out, "%Y-%m-%d")
                nights = (d2 - d1).days
                description = f"{nights} night(s) stay: {check_in} to {check_out} — {clean_room_type}"
            except Exception:
                description = f"Stay from {check_in} to {check_out} — {clean_room_type}"

        session = stripe.checkout.Session.create(
            mode="payment",
            expires_at=_expires_at,
            line_items=[
                {
                    "price_data": {
                        "currency": "aud",
                        "product_data": {
                            "name": product_name,
                            "description": description,
                        },
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            success_url=_success_url,
            cancel_url=_cancel_url,
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
