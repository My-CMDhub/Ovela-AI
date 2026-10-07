"""
Tool args carry guest names, emails and phone numbers; logs ship off-box.
These guard the paths that used to `logger.warning("ARGS DUMP: %s", args)`
or interpolate raw PII into log lines.
"""
import logging
from unittest.mock import MagicMock, AsyncMock

from services.voice_agent.functions import coalcreek_handlers
from services.voice_agent.functions.coalcreek_handlers import (
    CoalCreekFunctionDispatcher,
    _args_for_log,
    handle_create_booking_request,
)

NAME = "Zelda Quackenbush"
EMAIL = "zelda.quackenbush@example.com"
PHONE = "+61412345678"


def _assert_no_pii(caplog):
    text = "\n".join(r.getMessage() for r in caplog.records)
    for secret in (NAME, EMAIL, PHONE, "Quackenbush", "zelda.quackenbush"):
        assert secret not in text, f"PII {secret!r} leaked into logs:\n{text}"


def test_args_for_log_keeps_keys_and_safe_scalars_only():
    out = _args_for_log({
        "guest_name": NAME, "guest_email": EMAIL, "guest_phone": PHONE,
        "check_in_date": "2026-10-10", "room_type": "queen",
    })
    assert set(out) == {"guest_name", "guest_email", "guest_phone", "check_in_date", "room_type"}
    assert out["check_in_date"] == "2026-10-10" and out["room_type"] == "queen"
    assert NAME not in str(out) and EMAIL not in str(out) and PHONE not in str(out)
    assert _args_for_log(None) == {}


async def test_n1_gate_rejection_logs_no_pii(caplog):
    caplog.set_level(logging.DEBUG, logger=coalcreek_handlers.logger.name)
    result = await handle_create_booking_request(
        {
            "guest_name": NAME, "guest_email": EMAIL, "guest_phone": PHONE,
            "check_in_date": "2026-10-10", "check_out_date": "2026-10-11",
            "room_type": "queen", "has_user_confirmed_summary": "NO",
        },
        user_phone=PHONE,
        save_reservation_fn=None,
    )
    assert result["success"] is False
    assert caplog.records, "expected the N1 gate to log something"
    _assert_no_pii(caplog)


async def test_transfer_guard_logs_no_pii(caplog):
    caplog.set_level(logging.DEBUG, logger=coalcreek_handlers.logger.name)
    dispatcher = CoalCreekFunctionDispatcher(
        db_service=MagicMock(), user_phone=PHONE,
        save_reservation_fn=AsyncMock(), abuse_protection=MagicMock(),
    )
    result = await dispatcher.execute("transfer_to_staff", {
        "_user_utterance": "no", "guest_name": NAME, "guest_email": EMAIL,
    })
    assert result["success"] is False
    _assert_no_pii(caplog)


def test_not_your_booking_masks_caller_phone(caplog):
    caplog.set_level(logging.DEBUG, logger=coalcreek_handlers.logger.name)
    coalcreek_handlers.not_your_booking(
        "lookup_booking", {"booking_reference": "CC-1", "guest_name": NAME}, PHONE, "booking",
    )
    _assert_no_pii(caplog)
