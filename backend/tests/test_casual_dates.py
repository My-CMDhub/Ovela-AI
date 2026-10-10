"""
tests/test_casual_dates.py — dates the way callers say them, checked against
the dates the model sends.

The model turned "next weekend" into ISO dates from a prompt that said "this
weekend" and "next weekend" were the same dates, and that "next Monday" was
both the nearest Monday and next week's. Nothing checked it: the resolver in
the handlers only ran when the model sent no dates at all, which it never does.

Now the caller's own words are read (services/voice_agent/date_phrases.py) and
compared with the model's dates. These tests pin three things:

  readings     what each phrase means, on a fixed Wednesday and across a year
  restraint    words that are NOT a stay date never move a booking
  wiring       check_availability corrects and reads back; create_booking_request
               refuses to hold dates the caller just contradicted
"""
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.voice_agent import date_phrases as dp
from services.voice_agent.date_phrases import read_dates, reconcile

WED = date(2026, 10, 7)          # the Kaggle probe's "today": Wednesday 7 October 2026
D = date.fromisoformat


def _year():
    return [date(2026, 1, 1) + timedelta(days=n) for n in range(366)]


# ── what phrases mean, on Wednesday 7 October 2026 ──────────────────────────

@pytest.mark.parametrize("phrase, check_in, check_out, alternative", [
    ("this weekend", "2026-10-10", "2026-10-11", None),
    ("the weekend", "2026-10-10", "2026-10-11", None),
    ("next weekend", "2026-10-17", "2026-10-18", "2026-10-10"),
    ("weekend after next", "2026-10-24", "2026-10-25", "2026-10-17"),
    ("the last weekend of October", "2026-10-31", "2026-11-01", None),
    ("the first weekend of November", "2026-11-07", "2026-11-08", None),
    ("this Friday", "2026-10-09", None, None),
    ("Friday", "2026-10-09", None, None),
    ("on Friday night", "2026-10-09", None, None),
    ("next Friday", "2026-10-16", None, "2026-10-09"),
    ("next Saturday", "2026-10-17", None, "2026-10-10"),
    ("Friday week", "2026-10-16", None, None),
    ("Friday after next", "2026-10-16", None, "2026-10-23"),
    ("Tuesday next week", "2026-10-13", None, None),
    ("next week on Thursday", "2026-10-15", None, None),
    ("tonight", "2026-10-07", None, None),
    ("tomorrow night", "2026-10-08", None, None),
    ("the day after tomorrow", "2026-10-09", None, None),
    ("in three days", "2026-10-10", None, None),
    ("a week from today", "2026-10-14", None, None),
    ("this time next week", "2026-10-14", None, None),
    ("in a fortnight", "2026-10-21", None, None),
    ("in two weeks' time", "2026-10-21", None, None),
    ("the 5th", "2026-11-05", None, None),            # 5 October has passed
    ("the twenty first", "2026-10-21", None, None),
    ("the 31st", "2026-10-31", None, None),
    ("the 17th of October", "2026-10-17", None, None),
    ("October 30th", "2026-10-30", None, None),
    ("the 5th of next month", "2026-11-05", None, None),
    ("last Friday of the month", "2026-10-30", None, None),
    ("the 2nd Tuesday of November", "2026-11-10", None, None),
    ("Christmas", "2026-12-25", None, None),
    ("Christmas Eve", "2026-12-24", None, None),
    ("New Year's Eve", "2026-12-31", None, None),
    ("Boxing Day", "2026-12-26", None, None),
    ("Melbourne Cup", "2026-11-03", None, None),
    ("Anzac Day", "2027-04-25", None, None),           # 2026's has passed
    ("Good Friday", "2027-03-26", None, None),
    ("Easter Monday", "2027-03-29", None, None),
    # ranges and lengths
    ("Friday to Sunday", "2026-10-09", "2026-10-11", None),
    ("next Friday to Sunday", "2026-10-16", "2026-10-18", "2026-10-09"),
    ("from the 10th till the 12th", "2026-10-10", "2026-10-12", None),
    ("the 30th to the 2nd", "2026-10-30", "2026-11-02", None),
    ("Friday for two nights", "2026-10-09", "2026-10-11", None),
    ("Saturday for a couple of nights", "2026-10-10", "2026-10-12", None),
    ("tomorrow for a week", "2026-10-08", "2026-10-15", None),
])
def test_reading_on_a_wednesday(phrase, check_in, check_out, alternative):
    r = read_dates(phrase, WED)
    assert r is not None and not r.conflict and not r.past, (phrase, r)
    assert r.check_in == D(check_in), (phrase, r)
    if check_out:
        assert r.check_out == D(check_out), (phrase, r)
    assert r.alternative == (D(alternative) if alternative else None), (phrase, r)


@pytest.mark.parametrize("phrase, lo, hi", [
    ("next week", "2026-10-12", "2026-10-18"),
    ("this week", "2026-10-07", "2026-10-11"),
    ("end of the month", "2026-10-25", "2026-10-31"),
    ("end of next month", "2026-11-24", "2026-11-30"),
    ("mid November", "2026-11-11", "2026-11-20"),
    ("early December", "2026-12-01", "2026-12-10"),
    ("next month", "2026-11-01", "2026-11-30"),
    ("in December", "2026-12-01", "2026-12-31"),
])
def test_a_period_is_a_span_not_a_day(phrase, lo, hi):
    r = read_dates(phrase, WED)
    assert r.span == (D(lo), D(hi)) and r.check_in is None, (phrase, r)


@pytest.mark.parametrize("phrase, conflict", [
    ("Friday the 17th", "the 17th is a Saturday, not a Friday"),
    ("Friday the twenty first", "the 21st is a Wednesday, not a Friday"),
    ("February 30th", "there is no 30th of February"),
])
def test_a_contradiction_is_reported_not_resolved(phrase, conflict):
    assert read_dates(phrase, WED).conflict == conflict


def test_the_said_weekday_nearest_the_date_is_offered():
    r = read_dates("Friday the 17th", WED)
    assert r.alternative == D("2026-10-16")


def test_the_weekend_after_a_booking_is_after_the_booking_not_today():
    """The Kaggle probe's words: "Actually, can I move it to the weekend after instead?"."""
    booked = D("2026-10-16")
    r = read_dates("Actually, can I move it to the weekend after instead?", WED, anchor=booked)
    assert (r.check_in, r.check_out) == (D("2026-10-24"), D("2026-10-25"))
    # Without a booking to be "after", the phrase says nothing.
    assert read_dates("can I move it to the weekend after instead?", WED) is None


# ── across a whole year: the arithmetic only breaks on particular weekdays ──

@pytest.mark.parametrize("today", _year())
def test_weekends_are_saturdays_in_order(today):
    this = read_dates("this weekend", today).check_in
    nxt = read_dates("next weekend", today)
    after = read_dates("the weekend after next", today).check_in
    assert this.weekday() == nxt.check_in.weekday() == after.weekday() == 5
    assert today <= this and nxt.check_in - this == timedelta(days=7) and after - nxt.check_in == timedelta(days=7)
    # Two-way only early in the week; on a Friday or Saturday "next weekend" is plain.
    assert nxt.ambiguous == (today.weekday() not in (4, 5))


@pytest.mark.parametrize("today", _year())
def test_weekdays_land_on_the_right_day_and_never_in_the_past(today):
    for i, name in enumerate(dp.WEEKDAYS):
        this = read_dates(f"this {name}", today).check_in
        nxt = read_dates(f"next {name}", today)
        assert this.weekday() == nxt.check_in.weekday() == i
        assert today <= this < today + timedelta(days=7)
        assert nxt.check_in - this == timedelta(days=7)
        assert nxt.ambiguous == (i != today.weekday())
        assert nxt.alternative in (None, this)


@pytest.mark.parametrize("today", _year()[::7])
def test_every_day_of_the_month_is_its_next_occurrence(today):
    for day in range(1, 32):
        r = read_dates(f"the {day}{dp._suffix(day)}", today)
        assert r.check_in.day == day and today <= r.check_in < today + timedelta(days=62)


@pytest.mark.parametrize("today", _year()[::5])
def test_holidays_are_never_in_the_past(today):
    for phrase in ("christmas", "boxing day", "new year's eve", "anzac day", "good friday", "melbourne cup"):
        r = read_dates(phrase, today)
        assert today <= r.check_in <= today + timedelta(days=366), (phrase, today)


# ── restraint: words that must not move a booking ──────────────────────────

@pytest.mark.parametrize("words", [
    "the 2nd floor please",
    "my first name is Ann",
    "the first one sounds good",
    "is the twin on the 1st floor",
    "I may stay two more days, not sure",
    "the 10th to the 12th, can I check in tomorrow if I'm early?",  # a passing mention
    "Friday or Saturday, whichever is cheaper",                      # two unconnected days
])
def test_not_a_stay_date(words):
    r = read_dates(words, WED)
    assert r is None or (r.check_in is None and r.span is None), (words, r)


@pytest.mark.parametrize("words", ["we stayed last weekend", "we were there last Friday",
                                   "I checked out yesterday", "a week ago"])
def test_the_past_is_marked_past(words):
    assert read_dates(words, WED).past


@pytest.mark.parametrize("words", [
    "is breakfast included tomorrow",
    "is the pool open on Saturday",
    "what time is checkout on Sunday",
    "can I bring my dog next weekend",
])
def test_another_topic_never_overrides_the_models_dates(words):
    model = (D("2026-10-16"), D("2026-10-18"))
    rec = reconcile(*model, words, WED)
    assert (rec.check_in, rec.check_out) == model and not rec.ask and not rec.say_first, (words, rec)


# ── reconcile: the model's dates against the caller's words ────────────────

def test_a_wrong_next_weekend_is_corrected_and_read_back():
    """The live failure: "next weekend" booked as a weekend nobody asked for."""
    rec = reconcile(D("2026-10-03"), D("2026-10-04"), "anything free next weekend?", WED)
    assert (rec.check_in, rec.check_out) == (D("2026-10-17"), D("2026-10-18"))
    assert rec.changed and "Saturday the 17th" in rec.say_first and "not Saturday the 10th" in rec.say_first


def test_either_reading_of_a_two_way_phrase_is_kept_and_named():
    rec = reconcile(D("2026-10-10"), D("2026-10-11"), "next weekend please", WED)
    assert (rec.check_in, rec.check_out) == (D("2026-10-10"), D("2026-10-11")) and not rec.changed
    assert rec.say_first == "Just so we're on the same page, that's Saturday the 10th, not Saturday the 17th."


def test_a_right_unambiguous_date_is_left_alone_and_silent():
    rec = reconcile(D("2026-10-09"), D("2026-10-11"), "this Friday for two nights", WED)
    assert not rec.changed and rec.say_first == "" and not rec.ask


def test_the_number_of_nights_follows_the_caller():
    rec = reconcile(D("2026-10-09"), D("2026-10-10"), "two nights", WED)
    assert (rec.check_in, rec.check_out) == (D("2026-10-09"), D("2026-10-11"))


def test_a_contradiction_is_asked_about():
    rec = reconcile(D("2026-10-17"), D("2026-10-18"), "Friday the 17th", WED)
    assert rec.ask == ("Just to check — the 17th is a Saturday, not a Friday. "
                       "Did you mean Friday the 16th, or Saturday the 17th?")


def test_a_period_needs_a_day_unless_the_model_already_has_one_inside_it():
    asked = reconcile(None, None, "sometime next week", WED)
    assert "Which day" in asked.ask
    inside = reconcile(D("2026-10-13"), D("2026-10-14"), "next week", WED)
    assert inside.say_first == "That's Tuesday the 13th." and not inside.ask
    outside = reconcile(D("2026-10-20"), D("2026-10-21"), "next week", WED)
    assert outside.ask


# ── wiring through the real handlers ────────────────────────────────────────

import services.voice_agent.functions.coalcreek_handlers as H  # noqa: E402


@pytest.fixture
def wednesday():
    with patch.object(H, "_today_melbourne_date", lambda: WED):
        yield


async def test_check_availability_checks_the_dates_the_caller_meant(wednesday):
    seen = {}

    async def fake(args, db, context=None):
        seen.update(args)
        return {"available": True, "ai_should_say": "The Queen is available."}

    with patch.object(H, "_check_availability", fake):
        out = await H.handle_check_availability(
            {"check_in_date": "2026-10-10", "check_out_date": "2026-10-11", "room_type": "queen",
             "_user_utterance": "do you have anything the weekend after next?"}, MagicMock())
    # 10 Oct is neither reading of "the weekend after next" (24th, or 17th): corrected to the default.
    assert seen["check_in_date"] == "2026-10-24"
    assert out["ai_should_say"].startswith("Just so we're on the same page, that's Saturday the 24th")
    assert out["ai_should_say"].endswith("The Queen is available.")


async def test_check_availability_asks_instead_of_guessing(wednesday):
    inner = AsyncMock()
    with patch.object(H, "_check_availability", inner):
        out = await H.handle_check_availability(
            {"check_in_date": "2026-10-17", "check_out_date": "2026-10-18",
             "_user_utterance": "can I book Friday the 17th"}, MagicMock())
    inner.assert_not_awaited()
    assert out["dates_unclear"] is True and "Friday the 16th, or Saturday the 17th" in out["ai_should_say"]


async def test_check_availability_ignores_a_day_named_for_something_else(wednesday):
    seen = {}

    async def fake(args, db, context=None):
        seen.update(args)
        return {"available": True, "ai_should_say": "Yes."}

    with patch.object(H, "_check_availability", fake):
        out = await H.handle_check_availability(
            {"check_in_date": "2026-10-16", "check_out_date": "2026-10-18",
             "_user_utterance": "and is breakfast included tomorrow?"}, MagicMock())
    assert seen["check_in_date"] == "2026-10-16" and out["ai_should_say"] == "Yes."


async def test_create_booking_refuses_dates_the_caller_just_contradicted(wednesday):
    save = AsyncMock()
    out = await H.handle_create_booking_request(
        {"guest_name": "Ada Lovelace", "guest_email": "ada@example.com", "room_type": "queen",
         "check_in_date": "2026-10-10", "check_out_date": "2026-10-11", "has_user_confirmed_summary": "YES",
         "_user_utterance": "yes, the weekend after next is perfect"},
        "+61400000000", save, db_service=None)
    save.assert_not_awaited()
    assert out["success"] is False and out["dates_unclear"] is True
    assert "NOT BOOKED" in out["error"] and "Saturday the 24th of October" in out["error"]


async def test_create_booking_is_untouched_by_a_plain_yes(wednesday):
    """The usual case: the summary was read back and the caller said yes."""
    rec = H._reconcile_with_caller({"check_in_date": "2026-10-16", "check_out_date": "2026-10-18",
                                    "_user_utterance": "yes that's all correct"})
    assert rec[1:3] == ("", "") and rec[0]["check_in_date"] == "2026-10-16"


async def test_the_booked_check_in_reaches_the_date_tools():
    """So "the weekend after" can mean after the caller's booking."""
    from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator

    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock())
    agent.dispatcher = MagicMock()
    agent.dispatcher.execute = AsyncMock(return_value={"available": True})
    agent.call_state.identity_confirmed = True
    agent.call_state.check_in = "2026-10-16"

    await agent._execute_tool("check_availability", {"room_type": "queen"},
                              [{"role": "user", "content": "can I move it to the weekend after?"}])
    assert agent.dispatcher.execute.await_args.args[1]["_booking_check_in"] == "2026-10-16"


async def test_an_unidentified_caller_gets_no_booking_anchor():
    from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator

    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock())
    agent.dispatcher = MagicMock()
    agent.dispatcher.execute = AsyncMock(return_value={"available": True})
    agent.call_state.check_in = "2026-10-16"   # absorbed, but nobody was identified

    await agent._execute_tool("check_availability", {"room_type": "queen"},
                              [{"role": "user", "content": "the weekend after?"}])
    assert "_booking_check_in" not in agent.dispatcher.execute.await_args.args[1]


# ── found by the independent review (all reproduced before the fix) ─────────

SAT = date(2026, 10, 10)


@pytest.mark.parametrize("words, check_in, check_out", [
    ("I'd like to book the 24th to the 26th of November", "2026-11-24", "2026-11-26"),
    ("from the 24th to the 26th of December", "2026-12-24", "2026-12-26"),
    ("I want a room from the 4th to the 6th of December", "2026-12-04", "2026-12-06"),
    ("looking for a room for the 1st to the 3rd of January", "2027-01-01", "2027-01-03"),
    ("24th to 26th November", "2026-11-24", "2026-11-26"),
    ("24th-26th November", "2026-11-24", "2026-11-26"),
    ("twenty fourth to twenty sixth of november", "2026-11-24", "2026-11-26"),
    ("can I book Friday the 20th to Sunday the 22nd of November", "2026-11-20", "2026-11-22"),
])
def test_a_month_said_once_belongs_to_both_ends_of_the_range(words, check_in, check_out):
    r = read_dates(words, SAT)
    assert (r.check_in, r.check_out) == (D(check_in), D(check_out)) and not r.conflict, (words, r)


def test_this_weekend_keeps_a_friday_to_sunday_stay():
    rec = reconcile(D("2026-10-16"), D("2026-10-18"), "yes this weekend", date(2026, 10, 14))
    assert (rec.check_in, rec.check_out) == (D("2026-10-16"), D("2026-10-18")) and not rec.changed


def test_this_weekend_for_two_nights_is_friday_and_saturday():
    r = read_dates("this weekend, two nights", date(2026, 10, 14))
    assert (r.check_in, r.check_out) == (D("2026-10-16"), D("2026-10-18"))


@pytest.mark.parametrize("words", [
    "yes, this weekend is perfect",
    "yes, can I pay tomorrow",
    "I'll call you back tomorrow",
    "yes please, and can I check in early tomorrow",
])
def test_a_confirmation_turn_does_not_block_the_booking(words):
    # Booked for this weekend (said on Saturday the 10th, so it starts today).
    rec = reconcile(D("2026-10-10"), D("2026-10-11"), words, SAT, for_booking=True)
    assert not rec.changed and not rec.ask, (words, rec)


def test_a_change_said_at_confirmation_still_blocks():
    rec = reconcile(D("2026-10-17"), D("2026-10-18"), "actually make it the weekend after next", SAT,
                    for_booking=True)
    assert rec.changed and rec.check_in == D("2026-10-24")   # said on a Saturday: plain, not two-way


@pytest.mark.parametrize("words", [
    "can I book the first available date",
    "I'd like the first available room",
    "I'll take the second of those rooms",
    "May 2 people stay in the room",
])
def test_ordinals_and_may_that_are_not_dates(words):
    r = read_dates(words, SAT)
    assert r is None or (r.check_in is None and r.span is None), (words, r)


def test_a_week_on_friday_is_the_friday_after_this_one():
    assert read_dates("a week on Friday", WED).check_in == D("2026-10-16")
    on_the_day = read_dates("yes, a week on Saturday", SAT)
    assert on_the_day.check_in == D("2026-10-17") and on_the_day.alternative == D("2026-10-24")


def test_the_friday_after_needs_something_to_be_after():
    assert read_dates("the Friday after", WED) is None
    assert read_dates("the Friday after", WED, anchor=D("2026-10-16")).check_in == D("2026-10-23")


@pytest.mark.parametrize("words", [
    "over Christmas", "between christmas and new year", "Melbourne Cup weekend",
    "King's Birthday long weekend", "New Year's", "for Easter", "at our christmas party",
])
def test_a_holiday_season_is_not_a_check_in_day(words):
    assert read_dates(words, SAT) is None, words


@pytest.mark.parametrize("words, check_in", [
    ("no not this weekend - next weekend", "2026-10-17"),
    ("no, not this weekend — next weekend", "2026-10-17"),
    ("not friday, saturday", "2026-10-10"),   # Saturday said on a Saturday: today (next week is the alternative)
])
def test_a_correction_means_the_second_date(words, check_in):
    r = read_dates(words, SAT)
    assert r.check_in == D(check_in) and r.check_out in (None, D(check_in) + timedelta(days=1)), (words, r)
