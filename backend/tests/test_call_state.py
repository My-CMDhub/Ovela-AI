"""
tests/test_call_state.py — the call's memory, checked without the model.

CallState exists because tool results do not survive the turn that produced
them: the agent looked up the booking reference on turn 2 and, asked for it
again on turn 18, answered "I can't see the reference here" in 5 replays out
of 5. That is Track A — a reference read back wrong, or not at all, costs the
business a promise — so it is enforced in code and checked here, deterministically,
with no LLM in the loop. scripts/replay_conversation.py --only long-call
measures whether the agent then *uses* it; that is a rate, this is a guarantee.
"""

from datetime import date

import pytest

from services.voice_agent.call_state import (
    CallState, TRANSCRIPT_WINDOW, recent_transcript, stay_facts,
)

# What lookup_booking returns once a name the caller actually said has been
# matched in Python. Trimmed to the fields under test; shape copied from
# coalcreek_handlers._format_doc.
CONFIRMED = {
    "found": True, "found_by": "caller_phone",
    "booking_reference": "CC-76818", "guest_name": "Dhruv Patel",
    "guest_phone": "+61491570006", "guest_email": "dhruv.patel+stays@example.com",
    "room_type": "queen", "check_in_date": "2026-09-04",
    "check_out_date": "2026-09-06", "num_nights": 2,
    "total_amount": 358, "payment_status": "paid",
}

# The same booking, before anybody said who they were: the handler pops the
# three identifying fields and flags it.
UNCONFIRMED = {
    k: v for k, v in CONFIRMED.items()
    if k not in ("guest_name", "guest_phone", "guest_email")
} | {"identity_unconfirmed": True}

# A name that fits nobody on this number. The handler withholds the record.
MISMATCH = {"success": True, "found": False, "name_mismatch": True,
            "needs_reference": True, "message": "No reservation found under that name."}


def test_nothing_learned_yet_says_nothing():
    assert CallState().as_note() == ""


def test_confirmed_lookup_is_recalled_as_facts():
    state = CallState()
    state.observe("lookup_booking", {"guest_name": "Dhruv Patel"}, CONFIRMED)
    note = state.as_note()

    assert state.identity_confirmed
    # Everything the caller can ask for again fourteen turns later.
    for fact in ("CC-76818", "Dhruv Patel", "queen", "2026-09-04", "2026-09-06", "paid"):
        assert fact in note, f"{fact!r} missing from the note the model is given"


def test_unidentified_caller_gets_no_detail_carried_forward():
    """The handler withholds the guest's name from an unidentified caller. A
    note that carried the reservation forward anyway would quietly undo that."""
    state = CallState()
    state.observe("lookup_booking", {}, UNCONFIRMED)
    note = state.as_note()

    assert not state.identity_confirmed
    assert state.reservation_on_file
    assert "CC-76818" not in note
    assert "Dhruv" not in note
    assert "2026-09-04" not in note
    assert "NOT been identified" in note


def test_the_email_is_carried_once_identity_is_confirmed_the_phone_never():
    """Left out, the email was not fetched again when asked for: on a live call
    the agent said none was on file, then read back one it made up. A caller
    who has proven they are the guest hears their real address instead."""
    state = CallState()
    state.observe("lookup_booking", {"guest_name": "Dhruv Patel"}, CONFIRMED)
    note = state.as_note()

    assert "dhruv.patel+stays@example.com" in note
    assert "+61491570006" not in note


@pytest.mark.parametrize("result", [UNCONFIRMED, MISMATCH])
def test_no_email_is_carried_before_identity_is_confirmed(result):
    """The boundary that moved is 'after identity', not 'always'."""
    state = CallState()
    state.observe("lookup_booking", {"guest_name": "Sarah Wilkinson"},
                  dict(result, guest_email="dhruv.patel+stays@example.com"))
    assert "dhruv.patel+stays@example.com" not in state.as_note()


def test_a_name_that_does_not_fit_confirms_nothing():
    state = CallState()
    state.observe("lookup_booking", {"guest_name": "Sarah Wilkinson"}, MISMATCH)

    assert not state.identity_confirmed
    assert state.as_note() == ""


def test_a_later_mismatch_cannot_unpick_a_confirmed_identity():
    """Somebody asking about a second name mid-call must not wipe the booking
    the caller already proved was theirs."""
    state = CallState()
    state.observe("lookup_booking", {"guest_name": "Dhruv Patel"}, CONFIRMED)
    state.observe("lookup_booking", {"guest_name": "Sarah Wilkinson"}, MISMATCH)

    assert state.identity_confirmed
    assert "CC-76818" in state.as_note()


def test_a_completed_one_way_action_is_remembered_once():
    """'Did you already send that?' ten turns later must not be answered by a
    guess — and a repeated tool call must not read as two payment links."""
    state = CallState()
    ok = {"success": True}
    state.observe("resend_payment_link", {}, ok)
    state.observe("resend_payment_link", {}, ok)

    assert state.promises == ["the payment link was re-sent"]
    assert "the payment link was re-sent" in state.as_note()


def test_a_failed_one_way_action_is_not_a_promise():
    state = CallState()
    state.observe("resend_payment_link", {}, {"success": False, "error": "SMTP bounce"})

    assert state.promises == []


def test_booking_created_this_call_is_the_callers_own():
    state = CallState()
    state.observe("create_booking_request",
                  {"guest_name": "Ada Lovelace", "room_type": "twin"},
                  {"success": True, "booking_reference": "CC-90001",
                   "check_in_date": "2026-10-01", "check_out_date": "2026-10-03"})
    note = state.as_note()

    assert state.identity_confirmed
    assert "CC-90001" in note and "a booking was created" in note


def test_an_availability_answer_cannot_be_contradicted_later():
    state = CallState()
    state.observe("check_availability",
                  {"check_in_date": "2026-09-12", "check_out_date": "2026-09-14",
                   "room_type": "king"},
                  {"available": False})

    assert "2026-09-12 to 2026-09-14, king" in state.as_note()
    assert "nothing free" in state.as_note()


def test_a_junk_result_cannot_break_the_turn_that_produced_it():
    state = CallState()
    for junk in (None, "", [], {"found": True, "check_in_date": None}, {"available": "unknown"}):
        state.observe("lookup_booking", {}, junk)
        state.observe("check_availability", {}, junk)
    # No exception, and nothing invented.
    assert not state.identity_confirmed


def test_only_the_recent_transcript_is_replayed_verbatim():
    history = [{"role": "user", "content": str(n)} for n in range(60)]
    kept = recent_transcript(history)

    assert len(kept) == TRANSCRIPT_WINDOW
    assert kept[-1]["content"] == "59"          # the latest words are always there
    assert kept is not history                  # never hands back the live list


def test_a_short_call_is_replayed_whole():
    history = [{"role": "user", "content": "hello"}]
    assert recent_transcript(history) == history


# ── what the caller said, which nothing else in the system keeps ────────────
#
# For a guest with no record, their spelled-out name and email exist in exactly
# one place: whatever we choose to keep. update_guest_info answered "Details
# safely stored in my temporary memory for this call" and stored nothing, so
# the transcript was it — and the transcript is capped at TRANSCRIPT_WINDOW.
# Measured on replay_conversation --only new-caller-long: given on turn 3,
# needed on turn 17, lost 3 runs out of 3.

def test_what_the_caller_spelled_out_is_kept():
    state = CallState()
    state.heard({"guest_name": "Siobhan O'Connor", "guest_email": "s.oconnor-work@bigpond.com"})
    note = state.as_note()

    assert state.heard_name == "Siobhan O'Connor"
    assert "s.oconnor-work@bigpond.com" in note
    assert "NOT YET VERIFIED" in note


def test_it_is_never_presented_as_a_confirmed_fact():
    """The agent has to be able to tell "the database says this" from "I think
    I heard this", because only one of them is safe to book on."""
    state = CallState()
    state.heard({"guest_name": "Siobhan O'Connor"})

    assert not state.identity_confirmed
    assert "read it back for confirmation" in state.as_note()


def test_a_field_the_model_omits_does_not_erase_what_it_gave_before():
    """The model routinely re-sends a subset of the arguments. Treating a
    missing field as a deletion loses the email on the very next tool call."""
    state = CallState()
    state.heard({"guest_name": "Ada Lovelace", "guest_email": "ada@example.com"})
    state.heard({"guest_name": "Ada Lovelace"})            # email omitted
    state.heard({"guest_email": ""})                       # and blanked

    assert state.heard_email == "ada@example.com"


def test_junk_arguments_are_ignored():
    state = CallState()
    state.heard(None)
    state.heard({"guest_name": None, "guest_email": 42})
    assert state.heard_name == "" and state.heard_email == ""


# ── availability is perishable, and the note has to say so ─────────────────

def test_availability_is_not_offered_as_a_fact_to_answer_from():
    """The first version of this note said "do not look them up again unless
    the caller says something has changed" — which is right for a booking
    reference and wrong for a room, because another caller can take the last
    one between two turns of this conversation."""
    state = CallState()
    state.observe("check_availability",
                  {"check_in_date": "2026-09-12", "check_out_date": "2026-09-14"},
                  {"available": True})
    note = state.as_note()

    assert "CHECK AGAIN" in note
    assert "not necessarily true now" in note
    assert "do not" not in note.split("AVAILABILITY YOU ALREADY QUOTED")[1].lower() \
        or "do not contradict" in note


def test_a_settled_booking_is_still_offered_as_a_fact():
    """The split has to keep working in the other direction: a reference does
    not go stale, and telling the agent to re-check it would undo A1."""
    state = CallState()
    state.observe("lookup_booking", {"guest_name": "Dhruv Patel"}, CONFIRMED)
    note = state.as_note()

    assert "answer from them directly" in note
    assert "CC-76818" in note


# ── heard off the caller's own words, not off a tool argument ──────────────

def test_an_address_the_caller_spells_out_is_kept_without_any_tool():
    """heard() reads tool arguments, which only carry a detail when the model
    chooses to pass it. Measured on new-caller-long, the email was spelled out
    on turn 4, never reached a tool, and was gone by turn 17."""
    state = CallState()
    state.hear_caller("My email is s dot oconnor dash work at bigpond dot com.")

    assert state.heard_email == "s.oconnor-work@bigpond.com"
    assert "s.oconnor-work@bigpond.com" in state.as_note()


def test_an_ordinary_sentence_is_not_mistaken_for_an_address():
    state = CallState()
    state.hear_caller("I'd like a room at the motel, and that's all.")
    state.hear_caller("Sure, that's fine.")
    assert state.heard_email == ""


def test_a_corrected_address_replaces_the_first_one():
    """Callers misspeak and then fix it. The last one they said is the one."""
    state = CallState()
    state.hear_caller("it's ada at example dot com")
    state.hear_caller("sorry, it's ada dot lovelace at example dot com")
    assert state.heard_email == "ada.lovelace@example.com"


def test_hearing_junk_never_raises():
    state = CallState()
    for junk in (None, "", "   ", "at dot"):
        state.hear_caller(junk)
    assert state.heard_email == ""


# ── stay timing and the paid-booking rule, worked out in code ───────────────
#
# Measured on Kaggle, 6 models x 108 runs: asked to move a stay that had
# already ended, no model ever said it was over (0/108, twice) although today's
# date sat in the system prompt, and some offered to move it. With these two
# sentences placed next to the booking, offers to move a finished stay went
# 10-15 -> 0 and 50/108 said it was over. Date arithmetic is code's job.

TODAY = date(2026, 10, 5)


def test_a_stay_that_ended_is_said_to_be_over():
    timing, _ = stay_facts("2026-09-04", "2026-09-06", "pending_payment", TODAY)
    assert timing == ("Stay timing (worked out from today's date): this stay ended on "
                      "Sunday 6 September 2026. It is over and can't be moved or changed.")


def test_checking_out_today_counts_as_ended():
    timing, _ = stay_facts("2026-10-03", "2026-10-05", "paid", TODAY)
    assert "ended on Monday 5 October 2026" in timing


def test_a_stay_in_progress_says_when_it_checks_out():
    timing, _ = stay_facts("2026-10-05", "2026-10-07", "paid", TODAY)
    assert timing == ("Stay timing (worked out from today's date): in progress, "
                      "checking out Wednesday 7 October 2026.")


def test_an_upcoming_stay_says_when_it_starts():
    timing, _ = stay_facts("2026-10-06", "2026-10-08", "paid", TODAY)
    assert timing == ("Stay timing (worked out from today's date): upcoming, "
                      "starting Tuesday 6 October 2026.")


@pytest.mark.parametrize("status", ["paid", "card_on_file"])
def test_a_paid_booking_goes_to_reception_for_changes(status):
    _, rule = stay_facts("2026-10-06", "2026-10-08", status, TODAY)
    assert rule == ("Paid booking: dates, room or name can't be changed on this call; "
                    "reception makes changes to paid bookings.")


@pytest.mark.parametrize("status", ["pending_payment", "pending", "outstanding",
                                    "email_failed", "", None])
def test_an_unpaid_booking_can_still_be_changed(status):
    _, rule = stay_facts("2026-10-06", "2026-10-08", status, TODAY)
    assert rule == "Payment pending: dates or room can still be changed on this call."


def test_an_unpaid_stay_that_already_ended_is_not_called_changeable():
    # A no-show: the stay is over, so "can still be changed" would contradict the timing line.
    timing, rule = stay_facts("2026-09-04", "2026-09-06", "pending_payment", TODAY)
    assert "It is over and can't be moved or changed." in timing
    assert rule is None
    note = CallState(identity_confirmed=True, identity_basis="x", guest_name="A B",
                     booking_reference="KR-1", check_in="2026-09-04", check_out="2026-09-06",
                     payment_status="pending_payment").as_note(today=TODAY)
    assert "can still be changed" not in note


@pytest.mark.parametrize("check_in,check_out", [
    ("", ""), ("2026-10-06", ""), ("not a date", "2026-10-08"), (None, None),
    ("2026-13-40", "2026-10-08"),
])
def test_bad_dates_give_no_timing_and_never_raise(check_in, check_out):
    timing, rule = stay_facts(check_in, check_out, "paid", TODAY)
    assert timing is None
    assert rule.startswith("Paid booking")


def test_the_note_carries_both_facts_next_to_the_booking():
    state = CallState()
    state.observe("lookup_booking", {"guest_name": "Dhruv Patel"}, CONFIRMED)
    note = state.as_note(today=TODAY)

    assert ("- Stay timing (worked out from today's date): this stay ended on "
            "Sunday 6 September 2026. It is over and can't be moved or changed.") in note
    assert ("- Paid booking: dates, room or name can't be changed on this call; "
            "reception makes changes to paid bookings.") in note
    # Directly after the booking line, so the model reads them together.
    lines = note.splitlines()
    i = next(n for n, line in enumerate(lines) if line.startswith("- Their booking:"))
    assert lines[i + 1].startswith("- Stay timing")
    assert lines[i + 2].startswith("- Paid booking")


def test_no_booking_in_state_means_no_timing_lines():
    state = CallState()
    state.observe("lookup_booking", {}, UNCONFIRMED)
    note = state.as_note(today=TODAY)
    assert "Stay timing" not in note and "Paid booking" not in note


async def test_the_lookup_result_carries_both_facts(monkeypatch):
    """The model reads the tool result on the turn of the lookup, before the
    note exists — so the facts have to be in the result as well."""
    from unittest.mock import AsyncMock, MagicMock
    from services.voice_agent.functions import coalcreek_handlers as h

    monkeypatch.setattr(h, "_today_melbourne_date", lambda: TODAY)
    db = MagicMock()
    db.lookup_motel_reservation = AsyncMock(return_value=[{
        "booking_reference": "CC-76818", "guest_name": "Dhruv Patel",
        "guest_phone": "+61491570006", "room_type": "queen",
        "check_in_date": "2026-09-04", "check_out_date": "2026-09-06",
        "payment_status": "paid",
    }])
    result = await h.handle_lookup_booking({"guest_name": "Dhruv Patel"}, db, "+61491570006")

    assert result["found"]
    assert result["stay_status"] == (
        "Stay timing (worked out from today's date): this stay ended on "
        "Sunday 6 September 2026. It is over and can't be moved or changed.")
    assert result["change_policy"] == (
        "Paid booking: dates, room or name can't be changed on this call; "
        "reception makes changes to paid bookings.")
