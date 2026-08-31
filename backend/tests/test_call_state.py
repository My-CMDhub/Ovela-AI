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

from services.voice_agent.call_state import (
    CallState, TRANSCRIPT_WINDOW, recent_transcript,
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


def test_contact_details_are_never_carried():
    """lookup_booking releases these on the turn a name matched. Re-sending them
    in a system note on every later turn is a wider surface for no gain."""
    state = CallState()
    state.observe("lookup_booking", {"guest_name": "Dhruv Patel"}, CONFIRMED)
    note = state.as_note()

    assert "dhruv.patel+stays@example.com" not in note
    assert "+61491570006" not in note


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
