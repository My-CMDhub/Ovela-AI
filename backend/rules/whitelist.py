"""
Admin numbers that bypass the voice rate limits.

The numbers live in the environment, not here: publishing them tells a reader
exactly which callers skip the 2-calls-per-24h and 10-calls-per-hour limits.
Set ADMIN_WHITELIST_NUMBERS as a comma-separated E.164 list.
"""

import os


def parse_admin_numbers(raw: str | None) -> set[str]:
    """Parse the env value. An unset or empty value whitelists nobody."""
    return {n.strip() for n in (raw or "").split(",") if n.strip()}


ADMIN_NUMBERS = parse_admin_numbers(os.getenv("ADMIN_WHITELIST_NUMBERS"))


def is_whitelisted(phone_number: str) -> bool:
    """Check if a phone number is authorized to bypass limits."""
    if not phone_number:
        return False
    return phone_number in ADMIN_NUMBERS
