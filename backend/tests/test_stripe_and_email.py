"""
Tests for Stripe Automated Payment Handler.

Uses mocked Stripe SDK to verify session creation without real API calls.
"""
import pytest
from unittest.mock import patch, MagicMock


@patch("services.voice_agent.functions.stripe_handlers.stripe.checkout.Session.create")
def test_stripe_session_creation_returns_url(mock_stripe_create):
    """create_checkout_session returns the Stripe checkout URL."""
    mock_stripe_create.return_value = MagicMock(url="https://checkout.stripe.com/pay/cs_test_abc123")

    from services.voice_agent.functions.stripe_handlers import create_checkout_session
    url = create_checkout_session(amount_aud=150, room_type="queen")

    assert url == "https://checkout.stripe.com/pay/cs_test_abc123"


@patch("services.voice_agent.functions.stripe_handlers.stripe.checkout.Session.create")
def test_stripe_session_uses_correct_currency(mock_stripe_create):
    """Checkout session must use AUD currency."""
    mock_stripe_create.return_value = MagicMock(url="https://checkout.stripe.com/pay/cs_test_aud")

    from services.voice_agent.functions.stripe_handlers import create_checkout_session
    create_checkout_session(amount_aud=120, room_type="twin")

    call_kwargs = mock_stripe_create.call_args[1]
    line_item = call_kwargs["line_items"][0]
    assert line_item["price_data"]["currency"] == "aud"


@patch("services.voice_agent.functions.stripe_handlers.stripe.checkout.Session.create")
def test_stripe_session_converts_aud_to_cents(mock_stripe_create):
    """Amount must be converted from AUD dollars to cents (× 100)."""
    mock_stripe_create.return_value = MagicMock(url="https://checkout.stripe.com/pay/cs_test_cents")

    from services.voice_agent.functions.stripe_handlers import create_checkout_session
    create_checkout_session(amount_aud=95, room_type="queen")

    call_kwargs = mock_stripe_create.call_args[1]
    unit_amount = call_kwargs["line_items"][0]["price_data"]["unit_amount"]
    assert unit_amount == 9500  # $95 AUD in cents


@patch("services.voice_agent.functions.stripe_handlers.stripe.checkout.Session.create")
def test_stripe_session_product_name_includes_room_type(mock_stripe_create):
    """Product name in the checkout must include the room type for clarity."""
    mock_stripe_create.return_value = MagicMock(url="https://checkout.stripe.com/pay/cs_test_name")

    from services.voice_agent.functions.stripe_handlers import create_checkout_session
    create_checkout_session(amount_aud=160, room_type="spa")

    call_kwargs = mock_stripe_create.call_args[1]
    product_name = call_kwargs["line_items"][0]["price_data"]["product_data"]["name"]
    assert "spa" in product_name.lower() or "Spa" in product_name


@patch("services.voice_agent.functions.stripe_handlers.stripe.checkout.Session.create")
def test_stripe_session_returns_none_on_error(mock_stripe_create):
    """Stripe API failure returns None — never raises into the voice agent."""
    mock_stripe_create.side_effect = Exception("Stripe API timeout")

    from services.voice_agent.functions.stripe_handlers import create_checkout_session
    result = create_checkout_session(amount_aud=150, room_type="queen")

    assert result is None


@patch("services.voice_agent.functions.stripe_handlers.stripe.checkout.Session.create")
def test_stripe_session_mode_is_payment(mock_stripe_create):
    """Checkout session must be one-time 'payment' mode, not subscription."""
    mock_stripe_create.return_value = MagicMock(url="https://checkout.stripe.com/pay/cs_test_mode")

    from services.voice_agent.functions.stripe_handlers import create_checkout_session
    create_checkout_session(amount_aud=90, room_type="twin")

    call_kwargs = mock_stripe_create.call_args[1]
    assert call_kwargs["mode"] == "payment"


# ─── FIX 4: 30-min Stripe Expiry + SMTP Email Confirmation ───────────────────

import time as _time
import pytest


@patch("services.voice_agent.functions.stripe_handlers._STRIPE_CONFIGURED", True)
@patch("services.voice_agent.functions.stripe_handlers.stripe.checkout.Session.create")
def test_stripe_session_has_30min_expiry(mock_stripe_create):
    """Stripe checkout session must carry a 30-minute expiry (expires_at = now + 1800)."""
    mock_stripe_create.return_value = MagicMock(url="https://checkout.stripe.com/pay/cs_test_expiry")

    from services.voice_agent.functions.stripe_handlers import create_checkout_session

    before = int(_time.time()) + 1800
    create_checkout_session(amount_aud=150, room_type="queen", booking_ref="CC-99999")
    after = int(_time.time()) + 1800

    call_kwargs = mock_stripe_create.call_args[1]
    assert "expires_at" in call_kwargs, "expires_at must be passed to stripe.checkout.Session.create"
    assert before - 5 <= call_kwargs["expires_at"] <= after + 5, (
        f"expires_at={call_kwargs['expires_at']} should be approximately now+1800"
    )


@pytest.mark.asyncio
async def test_update_booking_payment_status_stores_expiry():
    """update_booking_payment_status must persist payment_expires_at to Appwrite PATCH payload."""
    from services.db.bookings import BookingsMixin

    class _FakeDB(BookingsMixin):
        def __init__(self):
            self.motel_db_id = "test_db"
            self._last_patch = None

        async def _motel_request(self, method, path, data=None, params=None):
            self._last_patch = (method, path, data)
            return {"$id": "doc_fake"}

    db = _FakeDB()
    expiry_ts = int(_time.time()) + 1800
    await db.update_booking_payment_status(
        booking_id="doc_fake",
        payment_status="pending_payment",
        payment_link_url="https://checkout.stripe.com/pay/cs_test",
        payment_expires_at=expiry_ts,
    )

    assert db._last_patch is not None, "PATCH was never called"
    method, path, payload = db._last_patch
    assert method == "PATCH"
    patch_data = payload["data"]
    assert patch_data.get("payment_status") == "pending_payment"
    assert patch_data.get("payment_link_url") == "https://checkout.stripe.com/pay/cs_test"
    assert patch_data.get("payment_expires_at") == expiry_ts


@pytest.mark.asyncio
@patch("services.voice_agent.functions.stripe_handlers.create_checkout_session", return_value="https://checkout.stripe.com/pay/cs_test_link")
async def test_stripe_link_updates_db_and_emails_guest(mock_checkout):
    """_handle_stripe_and_guest_email must PATCH Appwrite to pending_payment and email guest."""
    from unittest.mock import AsyncMock, patch as _patch
    from services.voice_agent.functions.coalcreek_handlers import _handle_stripe_and_guest_email

    mock_db = AsyncMock()
    mock_db.get_booking_by_reference.return_value = {"$id": "appwrite_doc_abc"}

    with _patch("services.email.email_service") as mock_email_svc:
        mock_email_svc.send_payment_link = AsyncMock(return_value=True)

        await _handle_stripe_and_guest_email(
            booking_ref="CC-12345",
            room_type="queen",
            total_amt=145,
            guest_email="guest@example.com",
            guest_name="John Smith",
            guest_phone="+61400000000",
            check_in="2026-06-01",
            check_out="2026-06-02",
            db_service=mock_db,
        )

    mock_db.get_booking_by_reference.assert_called_once_with("CC-12345")
    mock_db.update_booking_payment_status.assert_called_once()
    call_kwargs = mock_db.update_booking_payment_status.call_args
    assert call_kwargs[1].get("payment_status") == "pending_payment"
    assert call_kwargs[1].get("payment_link_url") == "https://checkout.stripe.com/pay/cs_test_link"
    assert "payment_expires_at" in call_kwargs[1]

    mock_email_svc.send_payment_link.assert_called_once()
    email_call = mock_email_svc.send_payment_link.call_args[1]
    assert email_call["to_email"] == "guest@example.com"
    assert email_call["booking_ref"] == "CC-12345"
    assert email_call["payment_link"] == "https://checkout.stripe.com/pay/cs_test_link"


@pytest.mark.asyncio
@patch("services.voice_agent.functions.stripe_handlers.create_checkout_session", return_value="https://checkout.stripe.com/pay/cs_test_link")
async def test_stripe_link_skips_email_when_no_guest_email(mock_checkout):
    """_handle_stripe_and_guest_email must skip guest email when guest_email is empty."""
    from unittest.mock import AsyncMock, patch as _patch
    from services.voice_agent.functions.coalcreek_handlers import _handle_stripe_and_guest_email

    mock_db = AsyncMock()
    mock_db.get_booking_by_reference.return_value = {"$id": "appwrite_doc_abc"}

    with _patch("services.email.email_service") as mock_email_svc:
        mock_email_svc.send_payment_link = AsyncMock(return_value=True)

        await _handle_stripe_and_guest_email(
            booking_ref="CC-12345",
            room_type="twin",
            total_amt=120,
            guest_email="",
            guest_name="Jane Doe",
            guest_phone="+61400000001",
            check_in="2026-06-05",
            check_out="2026-06-06",
            db_service=mock_db,
        )

    mock_email_svc.send_payment_link.assert_not_called()
    mock_db.update_booking_payment_status.assert_called_once()
