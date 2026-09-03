"""
tests/test_spelled_names.py — when a caller spells it, the letters win.

From a real call on 3 September. The recogniser produced:

    "My name is Siban O'Connor. That's s i o b h a n, then o, then
     apostrophe, c o n n o r."

Every spelled letter is correct. The phonetic guess beside it is not — and the
phonetic guess is what reached the database. The booking was written as
"Cyborn O'Connor", read back three times as natural speech, and confirmed
three times by a caller who could not hear the difference.

A caller who spells their name is telling you they expect the sound to be
wrong. Taking the sound anyway ignores the one piece of evidence they went out
of their way to give. Track A: a booking in the wrong name is a promise the
business cannot keep.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.voice_agent.call_state import CallState
from services.voice_agent.text_utils import extract_spelled_words, spelling_honoured

# Verbatim Deepgram output from the call. Not paraphrased — the whole point is
# that these are the strings the system actually has to cope with.
REAL_SPELLING = ("Alright. My name is Siban O'Connor. That's s i o b h a n, "
                 "then o, then apostrophe, c o n n o r.")
REAL_SURNAME_ONLY = "Okay. It is o then Epistroph, then c o n n o r."


class TestReadingTheLetters:
    def test_a_full_name_spelled_over_a_wrong_phonetic_guess(self):
        assert extract_spelled_words(REAL_SPELLING) == ["Siobhan", "O'Connor"]

    def test_apostrophe_as_the_recogniser_writes_it(self):
        """"Epistroph" is verbatim. A caller says "apostrophe" and this is what
        comes back."""
        assert extract_spelled_words(REAL_SURNAME_ONLY) == ["O'Connor"]

    def test_hyphenated_spelling(self):
        assert extract_spelled_words("That's S-I-O-B-H-A-N") == ["Siobhan"]

    def test_ordinary_speech_is_not_read_as_spelling(self):
        for said in ("A queen room from tenth September for two nights, I want.",
                     "Hi. I would like to book a room, please.",
                     "It's Dhruv Patel.",
                     "no, I mean what's check-in time?"):
            assert extract_spelled_words(said) == [], said

    def test_two_stray_letters_are_not_a_name(self):
        """"I" and "a" are words. A run has to be long enough to be deliberate."""
        assert extract_spelled_words("I a") == []


class TestHonouringIt:
    def test_the_written_name_must_keep_every_spelled_word(self):
        assert spelling_honoured("Siobhan O'Connor", "Siobhan O'Connor")
        assert not spelling_honoured("Siobhan O'Connor", "Cyborn O'Connor")

    def test_punctuation_and_case_are_not_differences(self):
        assert spelling_honoured("Siobhan O'Connor", "siobhan oconnor")

    def test_a_name_may_carry_more_than_was_spelled(self):
        """Callers often spell only the surname and say the first name."""
        assert spelling_honoured("O'Connor", "Siobhan O'Connor")

    def test_but_never_less(self):
        assert not spelling_honoured("Siobhan O'Connor", "O'Connor")

    def test_nothing_spelled_means_nothing_to_honour(self):
        assert spelling_honoured("", "whatever the model heard")


class TestTheNotepadKeepsTheSpelling:
    def test_the_spelling_is_recorded_and_marked_as_authoritative(self):
        state = CallState()
        state.hear_caller(REAL_SPELLING)
        note = state.as_note()

        assert state.spelled_name == "Siobhan O'Connor"
        assert "SPELLED OUT" in note
        assert "Siobhan O'Connor" in note

    def test_the_misheard_version_is_kept_but_labelled_unreliable(self):
        state = CallState()
        state.hear_caller(REAL_SPELLING)
        state.heard({"guest_name": "Cyborn O'Connor"})
        note = state.as_note()

        assert "unreliable" in note
        assert "Cyborn O'Connor" in note      # still visible, just not trusted


class TestTheGate:
    @pytest.fixture
    def agent(self):
        from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
        agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock())
        agent.dispatcher = MagicMock()
        agent.dispatcher.execute = AsyncMock(return_value={"success": True})
        agent.dispatcher.caller_reservation = AsyncMock(return_value=[])
        return agent

    CONFIRMED = [
        {"role": "assistant",
         "content": "Just to confirm, September 10th to the 12th, queen at $135 per night."},
        {"role": "user", "content": "Yes, go ahead."},
    ]

    @pytest.mark.asyncio
    async def test_a_booking_that_ignores_the_spelling_is_refused(self, agent):
        agent.call_state.hear_caller(REAL_SPELLING)

        result = await agent._execute_tool(
            "create_booking_request",
            {"guest_name": "Cyborn O'Connor", "has_user_confirmed_summary": "YES"},
            self.CONFIRMED)

        assert result["success"] is False
        agent.dispatcher.execute.assert_not_called()
        assert "Siobhan O'Connor" in result["error"]
        assert "one letter at a time" in result["error"]

    @pytest.mark.asyncio
    async def test_a_booking_that_uses_the_spelling_goes_through(self, agent):
        """The gate has to let the right answer past, or it has only traded a
        wrong booking for no booking."""
        agent.call_state.hear_caller(REAL_SPELLING)

        result = await agent._execute_tool(
            "create_booking_request",
            {"guest_name": "Siobhan O'Connor", "has_user_confirmed_summary": "YES"},
            self.CONFIRMED)

        assert result["success"] is True
        agent.dispatcher.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_a_caller_who_never_spelled_anything_is_unaffected(self, agent):
        result = await agent._execute_tool(
            "create_booking_request",
            {"guest_name": "Dhruv Patel", "has_user_confirmed_summary": "YES"},
            self.CONFIRMED)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_guest_info_is_held_to_the_same_spelling(self, agent):
        """It writes the name onto the reservation too."""
        agent.call_state.hear_caller(REAL_SPELLING)
        agent.call_state.identity_confirmed = True

        result = await agent._execute_tool(
            "update_guest_info", {"guest_name": "Cyborn O'Connor"}, [])

        assert result["success"] is False
        agent.dispatcher.execute.assert_not_called()
