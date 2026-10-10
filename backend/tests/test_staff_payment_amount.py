"""
tests/test_staff_payment_amount.py — a staff-generated payment link charges the
booking's own total, so the webhook's amount check confirms it.

The Stripe webhook holds a payment that differs from the booking's
total_amount by $1 or more for a person to check. The dashboard's Approve and
Regenerate-link buttons charged rate_per_night x num_nights instead (a flat
$145 when the rate was missing) and never read total_amount, so a dashboard
booking, or one whose total staff had edited, was paid and then held.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from api.dashboard import _staff_charge
from tests.test_dashboard_auth import TENANT, _booking, env  # noqa: F401  (fixture)


@pytest.mark.parametrize("booking, expected", [
    # The total wins over a rate that disagrees with it.
    ({"num_nights": 2, "rate_per_night": 145, "total_amount": 400}, (2, 200.0, 400.0)),
    # No total: charged from the rate.
    ({"num_nights": 3, "rate_per_night": 120}, (3, 120.0, 360.0)),
    # No total, no rate: the long-standing $145 fallback.
    ({"num_nights": 2}, (2, 145.0, 290.0)),
    # No num_nights (dashboard POST /reservations): counted from the dates.
    ({"check_in_date": "2030-01-10", "check_out_date": "2030-01-13", "total_amount": 300},
     (3, 100.0, 300.0)),
    # A zero or junk total is not a total.
    ({"num_nights": 1, "rate_per_night": 99, "total_amount": 0}, (1, 99.0, 99.0)),
    ({"num_nights": 1, "rate_per_night": 99, "total_amount": "n/a"}, (1, 99.0, 99.0)),
    # Nothing usable at all still charges one night, never zero.
    ({}, (1, 145.0, 145.0)),
    # Cents survive; whole totals are ints (see _whole_if_whole).
    ({"num_nights": 2, "total_amount": 239.5}, (2, 119.75, 239.5)),
])
def test_staff_charge(booking, expected):
    assert _staff_charge(booking) == expected


def test_a_whole_total_is_written_as_an_int():
    """total_amount may be an integer attribute in Appwrite, which rejects 400.0."""
    assert type(_staff_charge({"num_nights": 2, "total_amount": 400.0})[2]) is int
    assert type(_staff_charge({"num_nights": 2, "rate_per_night": 120.0})[2]) is int


async def test_a_total_that_does_not_divide_evenly_is_charged_to_the_cent():
    """$244 over 7 nights is 34.857… a night; int() of the product lost a cent."""
    from services.tenants.coalcreek.stripe import CoalCreekStripeService

    nights, rate, total = _staff_charge({"num_nights": 7, "total_amount": 244})
    svc = CoalCreekStripeService()
    svc.configured = True
    create = patch("stripe.checkout.Session.create",
                   return_value=SimpleNamespace(url="https://pay.example/s", id="cs_test_1"))
    with create as session_create:
        res = await svc.create_payment_link(
            booking_ref="CC-1", room_type="Queen", num_nights=nights, price_per_night=rate,
            customer_email=None, customer_name="Test Guest",
            check_in="2030-01-10", check_out="2030-01-13")
    assert res["success"] is True
    cents = session_create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"]
    assert cents == 24400 == round(total * 100)


def _stripe_link(monkeypatch):
    from services.tenants.coalcreek.stripe import coalcreek_stripe_service
    link = AsyncMock(return_value={"success": True, "payment_url": "https://pay.example/new"})
    monkeypatch.setattr(coalcreek_stripe_service, "create_payment_link", link)
    return link


def _charged_dollars(link) -> float:
    kw = link.await_args.kwargs
    return round(kw["price_per_night"] * kw["num_nights"], 2)


def _patched(appwrite) -> dict:
    patches = [c for c in appwrite.await_args_list if c.args[0] == "PATCH"]
    assert len(patches) == 1
    return patches[0].args[2]["data"]


def test_approve_charges_the_booking_total_and_records_it(env, monkeypatch):  # noqa: F811
    client, appwrite, db_service, _, sign_in = env
    sign_in(TENANT)
    db_service.get_tenant_config.return_value = {"use_stripe_payments": True,
                                                 "business_name": "A Motel"}
    link = _stripe_link(monkeypatch)
    # Check-in tomorrow: "payment" mode (a card hold beyond 7 days charges nothing).
    from datetime import datetime, timedelta
    ci = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    co = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    appwrite.side_effect = [
        _booking(TENANT, num_nights=2, rate_per_night=145, total_amount=400,
                 check_in_date=ci, check_out_date=co),
        {"$id": "b1"},
    ]

    resp = client.post("/api/dashboard/bookings/b1/approve")

    assert resp.status_code == 200, resp.text
    assert _charged_dollars(link) == 400.0
    data = _patched(appwrite)
    assert data["status"] == "link_sent"
    assert data["total_amount"] == 400.0


def test_regenerate_without_a_total_records_what_it_charged(env, monkeypatch):  # noqa: F811
    client, appwrite, _, _, sign_in = env
    sign_in(TENANT)
    link = _stripe_link(monkeypatch)
    appwrite.side_effect = [
        _booking(TENANT, status="approved", rate_per_night=120,
                 check_in_date="2030-01-10", check_out_date="2030-01-13"),
        {"$id": "b1"},
    ]

    resp = client.post("/api/dashboard/bookings/b1/payment-link")

    assert resp.json() == {"success": True, "payment_link": "https://pay.example/new"}
    assert _charged_dollars(link) == 360.0
    # The webhook compares the paid amount with this, so they must agree.
    assert _patched(appwrite)["total_amount"] == 360.0
