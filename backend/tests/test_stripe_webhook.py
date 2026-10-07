"""
tests/test_stripe_webhook.py — the Stripe webhook must not lose or repeat a payment.

Stripe delivers at-least-once and retries any non-2xx for up to three days, so
the status code IS the retry policy:

  - The handler used to answer 200 on every path, including when Appwrite failed
    to record the payment. Stripe then never redelivered, and a guest who had paid
    stayed `pending_payment` with no confirmation email. A failed write must be 5xx.
  - An unknown booking is permanent; 5xx there would retry a dead event for days.
  - A redelivered `checkout.session.completed` must not email the guest again.
  - `checkout.session.expired` only released staff-flow holds ("link_sent"); voice
    holds ("pending"/"reserved") stayed blocking a room forever. With stripe>=12
    the branch never ran at all: Event is no longer a dict and `.get` raised.

Signature verification is exercised for real down to construct_event, which is
the one thing monkeypatched (we cannot sign with Stripe's key here); it returns a
real stripe.Event so the handler sees the same object type production does.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import stripe
from fastapi import FastAPI
from fastapi.testclient import TestClient


DOC = {
    "$id": "doc1", "booking_reference": "CC-ABC123", "tenant_id": "coalcreek",
    "guest_email": "guest@example.com", "guest_name": "Test Guest",
    "room_type": "Queen Room", "check_in_date": "2026-10-10",
    "check_out_date": "2026-10-12", "num_nights": 2, "total_amount": 240,
    "status": "pending", "payment_status": "pending_payment",
}


def _event(event_type, **session):
    obj = {
        "id": "cs_test_1", "object": "checkout.session", "mode": "payment",
        "payment_intent": "pi_1", "amount_total": 24000, "created": 1_700_000_000,
        "customer_details": {"email": "guest@example.com"},
        "metadata": {"tenant_id": "coalcreek", "booking_ref": "CC-ABC123"},
    }
    obj.update(session)
    return {"id": "evt_test_1", "object": "event", "type": event_type, "data": {"object": obj}}


@pytest.fixture
def env(monkeypatch):
    """App with only the dashboard router, a verifying construct_event, and every
    DB/email call replaced by an AsyncMock the test can steer and inspect."""
    from core.config import settings
    from services.appwrite import db_service
    from services.email import email_service
    from api import dashboard

    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    sent = {}

    def construct_event(payload, sig_header, secret):
        # Mirror Stripe's contract: a missing/foreign signature or wrong secret raises.
        if sig_header != "good" or secret != "whsec_test":
            raise stripe.error.SignatureVerificationError("bad", sig_header)
        return stripe.Event.construct_from(json.loads(payload), "sk_test")

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(construct_event))

    mocks = {
        "find": AsyncMock(return_value=dict(DOC)),
        "pay": AsyncMock(return_value={"$id": "doc1"}),
        "patch": AsyncMock(return_value={"$id": "doc1"}),
        "guest_email": AsyncMock(return_value=True),
        "staff_email": AsyncMock(return_value=True),
    }
    monkeypatch.setattr(db_service, "find_booking_for_payment", mocks["find"])
    monkeypatch.setattr(db_service, "update_booking_payment_status", mocks["pay"])
    monkeypatch.setattr(db_service, "update_motel_reservation", mocks["patch"])
    monkeypatch.setattr(email_service, "send_guest_booking_confirmation", mocks["guest_email"])
    monkeypatch.setattr(email_service, "send_staff_payment_notification", mocks["staff_email"])

    app = FastAPI()
    app.include_router(dashboard.router, prefix="/api/motel")
    client = TestClient(app)

    def post(event, sig="good"):
        return client.post(
            "/api/motel/payments/webhook",
            content=json.dumps(event),
            headers={"stripe-signature": sig, "content-type": "application/json"},
        )

    mocks["post"] = post
    return mocks


# ── signature (unchanged behaviour, pinned) ──────────────────────────────────

def test_bad_signature_is_not_processed(env):
    r = env["post"](_event("checkout.session.completed"), sig="forged")
    assert r.status_code == 200 and r.json()["reason"] == "invalid_signature"
    env["find"].assert_not_called()
    env["pay"].assert_not_called()


def test_no_webhook_secret_means_nothing_verifies(env, monkeypatch):
    from core.config import settings
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    r = env["post"](_event("checkout.session.completed"))
    assert r.json()["reason"] == "invalid_signature"
    env["pay"].assert_not_called()


# ── checkout.session.completed ───────────────────────────────────────────────

def test_paid_booking_is_persisted_then_emailed(env):
    r = env["post"](_event("checkout.session.completed"))
    assert r.status_code == 200 and r.json()["status"] == "received"
    kwargs = env["pay"].await_args.kwargs
    assert kwargs["booking_id"] == "doc1" and kwargs["payment_status"] == "paid"
    assert kwargs["deposit_paid"] == 240.0
    env["guest_email"].assert_awaited_once()
    env["staff_email"].assert_awaited_once()


@pytest.mark.parametrize("failure", [AsyncMock(return_value=None),
                                     AsyncMock(side_effect=RuntimeError("appwrite down"))])
def test_persistence_failure_is_5xx_and_sends_nothing(env, monkeypatch, failure):
    """None (Appwrite error swallowed) and a raise both mean the payment is not
    recorded: Stripe must redeliver, and the guest must not be told it is
    confirmed before it is."""
    from services.appwrite import db_service
    monkeypatch.setattr(db_service, "update_booking_payment_status", failure)
    r = env["post"](_event("checkout.session.completed"))
    assert r.status_code >= 500
    env["guest_email"].assert_not_called()
    env["staff_email"].assert_not_called()


def test_lookup_failure_is_5xx(env):
    from services.db.bookings import BookingLookupError
    env["find"].side_effect = BookingLookupError("timeout")
    r = env["post"](_event("checkout.session.completed"))
    assert r.status_code == 503
    env["pay"].assert_not_called()


def test_unknown_booking_is_200_and_reported(env, monkeypatch, caplog):
    import sentry_sdk
    captured = []
    monkeypatch.setattr(sentry_sdk, "capture_message", lambda msg, **kw: captured.append(msg))
    env["find"].return_value = None
    with caplog.at_level("ERROR"):
        r = env["post"](_event("checkout.session.completed"))
    assert r.status_code == 200 and r.json()["reason"] == "booking_not_found"
    assert captured and "evt_test_1" in captured[0]
    assert any("evt_test_1" in rec.getMessage() and rec.levelname == "ERROR" for rec in caplog.records)
    env["pay"].assert_not_called()


def test_duplicate_completed_event_sends_no_second_email(env):
    env["post"](_event("checkout.session.completed"))
    # Second delivery: the booking now reads as paid, as Appwrite would return it.
    env["find"].return_value = dict(DOC, status="confirmed", payment_status="paid")
    r = env["post"](_event("checkout.session.completed"))
    assert r.status_code == 200 and r.json()["status"] == "duplicate"
    assert env["pay"].await_count == 1
    assert env["guest_email"].await_count == 1
    assert env["staff_email"].await_count == 1


def test_card_on_file_booking_still_processes_a_real_payment(env):
    env["find"].return_value = dict(DOC, status="confirmed", payment_status="card_on_file")
    r = env["post"](_event("checkout.session.completed"))
    assert r.json()["status"] == "received"
    env["pay"].assert_awaited_once()


def test_other_tenant_is_ignored_with_200(env):
    r = env["post"](_event("checkout.session.completed", metadata={"tenant_id": "other", "booking_ref": "X"}))
    assert r.status_code == 200
    env["find"].assert_not_called()


# ── checkout.session.expired ─────────────────────────────────────────────────

@pytest.mark.parametrize("hold_status", ["pending", "reserved"])
def test_expired_session_releases_unpaid_voice_hold(env, hold_status):
    env["find"].return_value = dict(DOC, status=hold_status)
    r = env["post"](_event("checkout.session.expired"))
    assert r.status_code == 200 and r.json()["status"] == "received"
    env["patch"].assert_awaited_once_with("doc1", {"status": "expired"})


def test_expired_session_keeps_staff_flow_expired_status(env):
    env["find"].return_value = dict(DOC, status="link_sent")
    env["post"](_event("checkout.session.expired"))
    env["patch"].assert_awaited_once_with("doc1", {"status": "expired"})


@pytest.mark.parametrize("doc", [
    dict(DOC, status="confirmed", payment_status="paid"),
    dict(DOC, status="pending", payment_status="paid"),          # status lagging the payment
    dict(DOC, status="reserved", payment_status="card_on_file"),
    dict(DOC, status="cancelled"),                               # guest cancelled
    dict(DOC, status="expired"),                                 # redelivery after release
])
def test_expired_session_never_touches_paid_or_settled_booking(env, doc):
    env["find"].return_value = doc
    r = env["post"](_event("checkout.session.expired"))
    assert r.status_code == 200
    env["patch"].assert_not_called()


def test_expired_session_keeps_hold_when_newer_link_was_sent(env):
    """resend_payment_link issues a new session; the old one expiring must not
    cancel a booking the guest can still pay through the new link."""
    later = datetime.fromtimestamp(1_700_000_000 + 900, tz=timezone.utc).isoformat()
    env["find"].return_value = dict(DOC, payment_link_sent_at=later)
    r = env["post"](_event("checkout.session.expired"))
    assert r.json()["reason"] == "superseded_session"
    env["patch"].assert_not_called()


def test_expired_session_release_failure_is_5xx(env):
    env["patch"].return_value = None
    r = env["post"](_event("checkout.session.expired"))
    assert r.status_code == 503


# ── find_booking_for_payment: transport failure vs genuine miss ──────────────

async def test_lookup_raises_when_appwrite_unreachable(monkeypatch):
    from services.appwrite import db_service
    from services.db.bookings import BookingLookupError
    monkeypatch.setattr(db_service, "_motel_request", AsyncMock(return_value=None))
    with pytest.raises(BookingLookupError):
        await db_service.find_booking_for_payment("CC-ABC123", "cs_test_1")


async def test_lookup_returns_none_for_genuine_miss(monkeypatch):
    from services.appwrite import db_service
    monkeypatch.setattr(db_service, "_motel_request", AsyncMock(return_value={"documents": [], "total": 0}))
    # The session-id fallback is best-effort: its attribute may not exist in the
    # schema, so its failure must read as "not found", not as a retryable error.
    monkeypatch.setattr(db_service, "get_booking_by_stripe_session", AsyncMock(return_value=None))
    assert await db_service.find_booking_for_payment("CC-ABC123", "cs_test_1") is None


async def test_lookup_returns_doc(monkeypatch):
    from services.appwrite import db_service
    monkeypatch.setattr(db_service, "_motel_request", AsyncMock(return_value={"documents": [DOC]}))
    assert (await db_service.find_booking_for_payment("CC-ABC123"))["$id"] == "doc1"


# ── review follow-ups: loud retries, double payments, exact supersession ──────

def test_a_failed_write_alerts_staff_once_however_often_stripe_retries(env, monkeypatch):
    """A permanent Appwrite rejection looks exactly like an outage, so 503 keeps
    Stripe retrying — but a person must hear about it, and only once."""
    from api import dashboard
    from services.email import email_service
    alerts = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_email", alerts, raising=False)
    monkeypatch.setattr(dashboard, "_ESCALATED_EVENTS", set())
    env["pay"].return_value = None

    codes = [env["post"](_event("checkout.session.completed")).status_code for _ in range(3)]

    assert codes == [503, 503, 503]
    assert alerts.await_count == 1
    assert "CC-ABC123" in alerts.await_args.kwargs["html_content"]
    env["guest_email"].assert_not_called()


def test_a_second_different_payment_is_flagged_not_swallowed(env, monkeypatch):
    from services.email import email_service
    alerts = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_email", alerts, raising=False)
    env["find"].return_value = dict(DOC, payment_status="paid", status="confirmed",
                                    stripe_payment_id="pi_OLD")

    r = env["post"](_event("checkout.session.completed", payment_intent="pi_NEW"))

    assert r.status_code == 200 and r.json()["status"] == "double_payment_flagged"
    assert alerts.await_count == 1 and "refund" in alerts.await_args.kwargs["subject"].lower()
    env["pay"].assert_not_called()


def test_the_same_payment_redelivered_is_still_a_quiet_duplicate(env, monkeypatch):
    from services.email import email_service
    alerts = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_email", alerts, raising=False)
    env["find"].return_value = dict(DOC, payment_status="paid", stripe_payment_id="pi_1")

    r = env["post"](_event("checkout.session.completed"))

    assert r.json()["status"] == "duplicate"
    alerts.assert_not_called()


def test_expiry_of_an_old_session_keeps_a_hold_whose_newer_link_is_live(env):
    """Resent 90s after the first link: inside the old two-minute grace, which
    released this hold while the guest could still pay the new link."""
    env["find"].return_value = dict(
        DOC, payment_link_url="https://checkout.stripe.com/c/pay/cs_test_NEW#abc",
        payment_link_sent_at=datetime.fromtimestamp(1_700_000_090, timezone.utc).isoformat())
    r = env["post"](_event("checkout.session.expired"))
    assert r.json()["reason"] == "superseded_session"
    env["patch"].assert_not_called()


def test_expiry_of_the_current_session_releases_the_hold(env):
    env["find"].return_value = dict(
        DOC, payment_link_url="https://checkout.stripe.com/c/pay/cs_test_1#abc",
        payment_link_sent_at=datetime.fromtimestamp(1_700_009_000, timezone.utc).isoformat())
    env["post"](_event("checkout.session.expired"))
    env["patch"].assert_awaited_once_with("doc1", {"status": "expired"})


def test_a_payment_on_an_expired_hold_is_flagged_not_confirmed(env, monkeypatch):
    """Its room went back on sale when the hold lapsed; confirming it blind
    could double-book. Money is real, so a person decides."""
    from services.email import email_service
    alerts = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_email", alerts, raising=False)
    env["find"].return_value = dict(DOC, status="expired")

    r = env["post"](_event("checkout.session.completed"))

    assert r.status_code == 200 and r.json()["status"] == "expired_hold_flagged"
    env["pay"].assert_not_called()
    assert alerts.await_count == 1


def test_a_stale_link_paid_after_the_stay_changed_is_flagged_not_confirmed(env, monkeypatch):
    """Extending a stay raises the total and mails a new link, but the first link
    stays payable at the old total. Paying it used to mark the longer stay paid."""
    from services.email import email_service
    alerts = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_email", alerts, raising=False)
    env["find"].return_value = dict(DOC, total_amount=360)      # extended to 3 nights

    r = env["post"](_event("checkout.session.completed", amount_total=24000))  # old 2-night link

    assert r.status_code == 200 and r.json()["status"] == "amount_mismatch_flagged"
    env["pay"].assert_not_called()
    assert alerts.await_count == 1


def test_dropped_cents_are_not_a_mismatch(env):
    """The voice path charges int(total); a $259.50 booking is paid as $259."""
    env["find"].return_value = dict(DOC, total_amount=259.5)
    r = env["post"](_event("checkout.session.completed", amount_total=25900))
    assert r.json()["status"] == "received"
    env["pay"].assert_awaited_once()


@pytest.mark.parametrize("released_as", ["rejected", "cancelled"])
def test_a_payment_on_a_rejected_or_cancelled_hold_is_flagged_not_confirmed(env, monkeypatch, released_as):
    """Staff reject a hold while the guest's 30-minute link is still live; the
    guest pays. The room was released on reject, so confirming could double-book."""
    from services.email import email_service
    alerts = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_email", alerts, raising=False)
    env["find"].return_value = dict(DOC, status=released_as)

    r = env["post"](_event("checkout.session.completed"))

    assert r.json()["status"] == f"{released_as}_hold_flagged"
    env["pay"].assert_not_called()
    assert alerts.await_count == 1
