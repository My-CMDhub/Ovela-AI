"""
conftest.py — pytest root configuration for the Ovela backend test suite.
Excludes manual integration tests that require live external services.
"""
import os

# Tests deliberately raise (MagicMock, "SMTP server offline", CC-12345). Without
# this they ship straight to the live Sentry project tagged environment:production.
os.environ["SENTRY_DSN"] = ""

collect_ignore_glob = [
    "scripts/*",                      # Ad-hoc dev scripts, not tests — several sys.exit() at import
    "tests/test_booking.py",          # Manual integration test — run directly with python -m
    "tests/test_stripe_live_flow.py", # Requires live Stripe + real DB
    "tests/fetch_logs.py",
    "tests/persist_eval.py",
    "tests/probe_gemini_25.py",
    "tests/trigger_emails.py",
]
