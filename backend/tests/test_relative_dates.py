"""
tests/test_relative_dates.py — the way people actually say dates.

Callers do not say "the tenth of September". They say "next Friday", "this
weekend", "Friday week". On a real call on Thursday 3 September the agent
answered "next weekend" with "the weekend of September 11th and 12th" — which
is neither next weekend (the 12th and 13th) nor a weekend.

The resolver had two faults that reinforced each other:

  "this weekend" and "next weekend" returned the SAME date, and so did "this
  Friday" and "next Friday" — every qualifier collapsed to the next occurrence.

  the phrase branches were checked BEFORE the explicit ISO dates, so a caller
  who gave real dates and then said "can I check in tomorrow if I'm early?"
  had their booking moved to tomorrow.

Swept over a full year rather than the handful of days someone thinks to type,
because the arithmetic only changes on particular weekdays.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

import services.voice_agent.functions.coalcreek_handlers as H

SATURDAY = 5


def resolve(phrase, today, check_in="", check_out=""):
    with patch.object(H, "_today_melbourne_date", lambda: today):
        return H._resolve_relative_dates(check_in, check_out, phrase)


def a_year_of_days():
    start = date(2026, 1, 1)
    return [start + timedelta(days=n) for n in range(365)]


class TestThisAndNextAreDifferentDays:
    @pytest.mark.parametrize("today", a_year_of_days())
    def test_next_weekend_is_exactly_a_week_after_this_weekend(self, today):
        this_sat, _, _ = resolve("this weekend", today)
        next_sat, _, _ = resolve("next weekend", today)
        assert next_sat - this_sat == timedelta(days=7), today

    @pytest.mark.parametrize("today", a_year_of_days())
    def test_a_weekend_is_a_saturday(self, today):
        for phrase in ("this weekend", "next weekend", "upcoming weekend"):
            check_in, check_out, _ = resolve(phrase, today)
            assert check_in.weekday() == SATURDAY, (phrase, today)
            assert check_out == check_in + timedelta(days=1)

    @pytest.mark.parametrize("today", a_year_of_days())
    def test_next_friday_is_a_week_after_this_friday(self, today):
        this_fri, _, _ = resolve("this friday", today)
        next_fri, _, _ = resolve("next friday", today)
        assert next_fri - this_fri == timedelta(days=7), today

    @pytest.mark.parametrize("today", a_year_of_days())
    def test_this_weekday_lands_on_that_weekday_and_is_never_in_the_past(self, today):
        for word, index in (("monday", 0), ("friday", 4), ("sunday", 6)):
            resolved, _, _ = resolve(f"this {word}", today)
            assert resolved.weekday() == index, (word, today)
            assert resolved >= today, (word, today)

    def test_this_x_said_on_an_x_means_today(self):
        thursday = date(2026, 9, 3)
        assert resolve("this thursday", thursday)[0] == thursday


class TestTheDayTheCallsWereMade:
    """Thursday 3 September 2026. The agent said "September 11th and 12th"."""

    TODAY = date(2026, 9, 3)

    @pytest.mark.parametrize("phrase,expected", [
        ("this weekend", date(2026, 9, 5)),
        ("next weekend", date(2026, 9, 12)),
        ("this friday", date(2026, 9, 4)),
        ("next friday", date(2026, 9, 11)),
        ("tomorrow", date(2026, 9, 4)),
        ("today", date(2026, 9, 3)),
    ])
    def test_the_phrase_resolves_to_the_day_a_person_would_name(self, phrase, expected):
        assert resolve(phrase, self.TODAY)[0] == expected


class TestAnExplicitDateWins:
    TODAY = date(2026, 9, 3)

    def test_a_stray_relative_word_does_not_move_a_real_booking(self):
        """Verbatim shape of the trap: real dates, then an aside."""
        check_in, check_out, source = resolve(
            "the 10th to the 12th, oh and can I check in tomorrow if I'm early?",
            self.TODAY, check_in="2026-09-10", check_out="2026-09-12")

        assert (check_in, check_out) == (date(2026, 9, 10), date(2026, 9, 12))
        assert source == "iso"

    @pytest.mark.parametrize("aside", ["tomorrow", "next weekend", "this friday",
                                       "today", "in 3 days"])
    def test_no_phrase_beats_an_explicit_date(self, aside):
        check_in, _, source = resolve(aside, self.TODAY,
                                      check_in="2026-10-01", check_out="2026-10-03")
        assert check_in == date(2026, 10, 1), aside
        assert source == "iso"

    def test_a_one_night_stay_gets_a_checkout(self):
        _, check_out, _ = resolve("", self.TODAY, check_in="2026-10-01")
        assert check_out == date(2026, 10, 2)


class TestAmbiguityIsFlaggedRatherThanGuessed:
    """"Next Friday" on a Wednesday means different things to different people,
    and the cost of guessing is a guest arriving a week out. The resolver still
    answers — it just says the answer needs confirming."""

    def test_next_weekday_is_marked_ambiguous(self):
        assert resolve("next friday", date(2026, 9, 3))[2] == "weekday_phrase_ambiguous"

    def test_this_weekday_is_not(self):
        assert resolve("this friday", date(2026, 9, 3))[2] == "weekday_phrase"

    def test_next_x_said_on_an_x_is_unambiguous(self):
        """On a Thursday, "next Thursday" is the only Thursday it can mean."""
        assert resolve("next thursday", date(2026, 9, 3))[2] == "weekday_phrase"


class TestNothingToResolve:
    def test_ordinary_speech_resolves_nothing(self):
        for said in ("do you have parking?", "my name is Dhruv Patel", ""):
            assert resolve(said, date(2026, 9, 3))[2] == "unresolved"


class TestTheResolverActuallyRunsOnTheLivePath:
    """
    It never did. The handlers read the caller's words from `_user_utterance`,
    and only the legacy monolithic handler ever set it — so on the cascaded
    path that answers the phone, `context` was absent, the argument was absent,
    and every relative date was resolved by the model with nothing checking it.
    A tested resolver that is never called is the same as no resolver.
    """

    @pytest.mark.asyncio
    async def test_the_callers_words_reach_the_date_handlers(self):
        from unittest.mock import AsyncMock, MagicMock
        from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator

        agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock())
        agent.dispatcher = MagicMock()
        agent.dispatcher.execute = AsyncMock(return_value={"available": True})

        history = [{"role": "user", "content": "anything free next weekend?"}]
        await agent._execute_tool("check_availability", {"room_type": "queen"}, history)

        sent = agent.dispatcher.execute.await_args.args[1]
        assert sent["_user_utterance"] == "anything free next weekend?"

    @pytest.mark.asyncio
    async def test_a_read_only_tool_is_not_given_the_utterance(self):
        """Only the two handlers that resolve dates read it. Threading it
        everywhere would be a wider blast radius for no gain."""
        from unittest.mock import AsyncMock, MagicMock
        from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator

        agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock())
        agent.dispatcher = MagicMock()
        agent.dispatcher.execute = AsyncMock(return_value={"found": False})

        await agent._execute_tool("lookup_booking", {"guest_name": "Ada"},
                                  [{"role": "user", "content": "it's Ada"}])

        assert "_user_utterance" not in agent.dispatcher.execute.await_args.args[1]
