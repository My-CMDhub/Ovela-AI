"""
Stripe webhook — intentionally empty router.

The live handler is POST /api/motel/payments/webhook (also /api/dashboard/...),
`stripe_webhook` in api/dashboard.py.

This module used to hold a second `stripe_webhook` meant for /api/stripe/webhook,
but it never had an @router decorator, so FastAPI never registered it and any
Stripe endpoint pointed at that URL got a 404. Nothing referenced the function,
so it was removed rather than left as a trap: it emailed the guest even when the
booking write failed and had no duplicate-delivery guard, so re-adding the
decorator would have reintroduced double emails and silently lost payments.
Only one webhook URL should be registered with Stripe; use the dashboard one.

The empty router stays because main.py still includes it.
"""

from fastapi import APIRouter

router = APIRouter()
