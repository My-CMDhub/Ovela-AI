"""
Two things the agent should know before the caller says a word, and one thing
it must not say.

The caller's number is the only identifier on a phone call that the speech
recogniser cannot corrupt. Looking the booking up at call setup and holding it
turns the name the caller speaks into a *confirmation* of an identity we
already have, instead of a search key — which is the unsafe direction, because
Flux transcribes one real guest's name as another real guest's name.

Holding it is not the same as announcing it. A number can be shared by a
couple, a family or an office line, so greeting whoever answers by name leaks
both that the number has a booking and whose it is.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.voice_agent.prompts_coalcreek import build_caller_context_note

BOOKING = {
    "guest_name": "Dhruv Patel",
    "booking_reference": "CC-76818",
    "room_type": "queen",
    "check_in_date": "2026-09-02",
    "check_out_date": "2026-09-04",
    "status": "confirmed",
    "payment_status": "paid",
}


# --- what the model is told ---------------------------------------------------

def test_no_booking_on_this_number_means_no_note():
    """Silence, not a note saying we found nothing — that is prompt for nothing."""
    assert build_caller_context_note([]) == ""


def test_the_note_never_carries_the_guests_identity():
    """
    The measured reason: with the name in the note, the agent volunteered it on
    turn one in four runs out of five under light speech degradation, before the
    caller had said anything about who they were. A model asked to hold a secret
    it can see will eventually say it. So it does not get to see it.
    """
    note = build_caller_context_note([BOOKING])
    for secret in ("Dhruv", "Patel", "CC-76818", "2026-09-02", "queen"):
        assert secret not in note, f"note leaks {secret!r} into the model's context"


def test_the_note_still_says_a_booking_exists():
    """Without this the agent treats a returning guest as a stranger."""
    note = build_caller_context_note([BOOKING]).lower()
    assert "reservation" in note


def test_the_note_forbids_volunteering_the_name():
    note = build_caller_context_note([BOOKING]).lower()
    assert "not been told" in note
    assert "must not guess" in note


def test_the_note_routes_confirmation_through_the_tool():
    """The name is matched in Python, not judged from context the model holds."""
    note = build_caller_context_note([BOOKING]).lower()
    assert "lookup_booking" in note
    assert "tool decides" in note


def test_several_bookings_on_one_number_are_counted_not_listed():
    second = dict(BOOKING, booking_reference="CC-99001", check_in_date="2026-10-01")
    note = build_caller_context_note([BOOKING, second])
    assert "2 reservations" in note
    assert "CC-99001" not in note


# --- the prefetch actually keeping its answer ---------------------------------

@pytest.mark.asyncio
async def test_the_prefetched_booking_is_kept_not_discarded():
    from services.voice_agent.functions.coalcreek_handlers import CoalCreekFunctionDispatcher

    db = AsyncMock()
    db.lookup_motel_reservation = AsyncMock(return_value=[BOOKING])
    dispatcher = CoalCreekFunctionDispatcher(
        db_service=db, user_phone="+61481131771",
        save_reservation_fn=lambda data: None, abuse_protection=None,
    )
    dispatcher.prefetch_caller_reservation()
    assert await dispatcher.caller_reservation() == [BOOKING]


@pytest.mark.asyncio
async def test_no_caller_number_means_nothing_to_hold():
    from services.voice_agent.functions.coalcreek_handlers import CoalCreekFunctionDispatcher

    db = AsyncMock()
    dispatcher = CoalCreekFunctionDispatcher(
        db_service=db, user_phone="", save_reservation_fn=lambda data: None,
        abuse_protection=None,
    )
    dispatcher.prefetch_caller_reservation()
    assert await dispatcher.caller_reservation() == []
    db.lookup_motel_reservation.assert_not_awaited()


# --- the outbound email kill switch -------------------------------------------

@pytest.mark.asyncio
async def test_disabling_email_stops_the_send_without_failing_the_booking(monkeypatch, caplog):
    """
    Off means "did not leave the building", not "errored". A failure here would
    make the agent offer to resend a link on every test call.
    """
    from core.config import settings
    from services.email import EmailService

    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    smtp_attempted = False

    import aiosmtplib

    def explode(*a, **kw):
        nonlocal smtp_attempted
        smtp_attempted = True
        raise AssertionError("SMTP must not be touched while email is disabled")

    monkeypatch.setattr(aiosmtplib, "SMTP", explode)

    with caplog.at_level("WARNING"):
        sent = await EmailService().send_email(
            "guest@example.com", "Your booking", "<p>hi</p>"
        )

    assert sent is True
    assert smtp_attempted is False
    assert "guest@example.com" in caplog.text
    assert "Your booking" in caplog.text


# --- the note reaching the model, which is the only thing that matters --------

def _delta(content):
    from unittest.mock import MagicMock
    ev = MagicMock()
    ev.choices = [MagicMock()]
    ev.choices[0].delta.content = content
    ev.choices[0].delta.tool_calls = None
    return ev


async def _messages_sent(caller_docs):
    """Drive one real turn and hand back what was actually sent to the model."""
    from unittest.mock import MagicMock
    from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator

    async def fake_stream(*_a, **_kw):
        yield _delta("Hi there.")

    orch = CascadedPipelineOrchestrator(twilio_ws=MagicMock())
    orch._context_ready = True
    orch.tenant_config = {"voice_settings": {"llm_model": "gpt-4.1-nano"}}
    orch.dispatcher = MagicMock()
    orch.dispatcher.caller_reservation = AsyncMock(return_value=caller_docs)
    orch._openai = MagicMock()
    orch._openai.chat.completions.create = AsyncMock(return_value=fake_stream())

    [c async for c in orch._default_llm_callback([{"role": "user", "content": "hi"}])]
    return orch._openai.chat.completions.create.call_args.kwargs["messages"]


@pytest.mark.asyncio
async def test_the_model_is_told_who_the_number_belongs_to():
    messages = await _messages_sent([BOOKING])
    assert any("CALLER ON FILE" in m["content"] for m in messages if m["role"] == "system")


@pytest.mark.asyncio
async def test_an_unknown_number_adds_no_system_message():
    messages = await _messages_sent([])
    assert len([m for m in messages if m["role"] == "system"]) == 1


@pytest.mark.asyncio
async def test_the_note_sits_after_the_cached_prompt_never_in_front_of_it():
    """
    The big prompt is the cached prefix. A per-call note in front of it changes
    the first bytes of every call and throws the prompt cache away.
    """
    messages = await _messages_sent([BOOKING])
    assert "CALLER ON FILE" not in messages[0]["content"]
    assert "CALLER ON FILE" in messages[1]["content"]


@pytest.mark.asyncio
async def test_a_booking_found_by_phone_alone_arrives_without_the_guests_identity():
    """
    Before the caller has said who they are, the agent needs the stay details to
    be useful and does not need the name. Withholding it is stronger than
    instructing against it: under a degraded transcript the model repeated a
    name it had been shown, even though the prompt forbade it. It cannot repeat
    what it was never given.
    """
    from services.voice_agent.functions.coalcreek_handlers import handle_lookup_booking

    db = MagicMock()
    db.lookup_motel_reservation = AsyncMock(return_value=[dict(
        BOOKING, guest_phone="+61481131771", guest_email="dhruv.patel+stays@example.com")])

    result = await handle_lookup_booking({}, db, "+61481131771")

    assert result.get("found") is True
    assert result.get("check_in_date")            # still useful
    blob = str(result)
    for secret in ("Dhruv", "Patel", "dhruv.patel", "+61481131771"):
        assert secret not in blob, f"leaked {secret!r} before the caller identified themselves"
