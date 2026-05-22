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
