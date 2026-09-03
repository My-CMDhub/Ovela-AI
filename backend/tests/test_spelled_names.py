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


class TestASpellingMustBeANameToCount:
    """
    Found in review, and it was the more dangerous half of the spelling fix.

    Callers spell emails and references far more often than names, and the
    letters are indistinguishable. "j o h n s m i t h at gmail dot com"
    assembled into a name called "Johnsmith" — which then failed
    spelling_honoured against every correctly-written name for the REST of the
    call, because spelled_name is never cleared. So the gate either refused
    every real name, or the model obeyed the refusal and wrote "Johnsmith" onto
    the booking and the payment email.

    The cue that separates them is usually in the agent's question, not the
    caller's answer: "It is o then Epistroph, then c o n n o r" is only a name
    because the agent had just asked for one.
    """

    @pytest.mark.parametrize("said,asked", [
        ("Yeah it's j o h n s m i t h at gmail dot com", "And your email?"),
        ("d p p a t e l 2 0 0 0 4 at gmail dot com", "What's your email address?"),
        ("the reference is C C dash A B C D E F", "Do you have your booking reference?"),
        ("it's m c k e n z i e street", "What's the address?"),
    ])
    def test_letters_that_are_not_a_name_are_not_taken_as_one(self, said, asked):
        state = CallState()
        state.hear_caller(said, agent_asked=asked)
        assert state.spelled_name == ""

    def test_an_address_claims_the_sentence_before_a_name_can(self):
        """The same letters cannot be both. Asked for a name and given an
        address, the address wins and no name is recorded — the alternative is
        a name called "Johnsmith" blocking the booking gate for the rest of the
        call."""
        state = CallState()
        state.hear_caller("my email is j o h n at gmail dot com",
                          agent_asked="And your name?")

        assert state.heard_email == "john@gmail.com"
        assert state.spelled_name == ""

    def test_the_cue_may_come_from_the_agents_question(self):
        state = CallState()
        state.hear_caller("Okay. It is o then Epistroph, then c o n n o r.",
                          agent_asked="Could you please spell your last name for me?")
        assert state.spelled_name == "O'Connor"

    def test_the_cue_may_come_from_the_callers_own_sentence(self):
        state = CallState()
        state.hear_caller(REAL_SPELLING)
        assert state.spelled_name == "Siobhan O'Connor"


class TestTheGateComparesLettersNotWordBreaks:
    """A caller who spells straight through, with no filler between the words,
    assembles as one run — and a word-by-word check then refused the very name
    that had just been spelled."""

    @pytest.mark.parametrize("spelled,written", [
        ("Siobhanoconnor", "Siobhan O'Connor"),
        ("Maryannesmith", "Mary Anne Smith"),
        ("Davidjones", "David Jones"),
    ])
    def test_where_the_words_divide_is_not_evidence(self, spelled, written):
        assert spelling_honoured(spelled, written)

    def test_and_a_genuinely_different_name_is_still_refused(self):
        assert not spelling_honoured("Siobhan O'Connor", "Cyborn O'Connor")
