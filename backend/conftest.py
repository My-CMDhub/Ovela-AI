"""
conftest.py — pytest root configuration for the Ovela backend test suite.
Excludes manual integration tests that require live external services.
"""
collect_ignore_glob = [
    "tests/test_booking.py",          # Manual integration test — run directly with python -m
    "tests/test_stripe_live_flow.py", # Requires live Stripe + real DB
    "tests/fetch_logs.py",
    "tests/persist_eval.py",
    "tests/probe_gemini_25.py",
    "tests/trigger_emails.py",
]
