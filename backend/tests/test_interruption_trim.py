"""
tests/test_interruption_trim.py
================================
Phase 12.1 — RED-state failing unit tests for Twilio mark-tracking
and interruption text-trimming logic.

These tests are written BEFORE the implementation module
(services/voice_agent/interruption.py) exists. Every test MUST fail
with ImportError or AssertionError until GREEN is reached.

Scenarios covered:
  Scenario 1 — Mathematical Interruption Trimming (Pruning)
  ─────────────────────────────────────────────────────────
  - mark_tracker.register_word maps word indices to mark names correctly
  - mark_tracker.confirm_mark updates last_confirmed_word_index
  - mark_tracker.confirmed_index returns 0 when no marks received
  - slice_to_confirmed_word returns empty string when nothing confirmed
  - slice_to_confirmed_word preserves confirmed words and discards the rest
  - slice_to_confirmed_word is word-boundary-accurate (no partial words)
  - slice_to_confirmed_word with all words confirmed returns full text
  - conversation history pruning: un-heard words removed from last assistant turn
  - conversation history pruning: multiple turns preserved before last assistant
  - pruning a history with no assistant turn returns history unchanged

  Scenario 2 — State-Aware Backchannel Routing
  ─────────────────────────────────────────────
  - AGENT_SPEAKING + backchannel → no LLM trigger (route_transcript returns "ignore")
  - AGENT_SPEAKING + interruption word → route_transcript returns "interrupt"
  - AWAITING_INPUT + single "yes" → route_transcript returns "forward"
  - AWAITING_INPUT + long utterance → route_transcript returns "forward"

  Scenario 4 — Cognitive Delay & Barge-In Immunity
  ─────────────────────────────────────────────────
  - cognitive_delay returns 0 when tool call exceeded MIN_ACTION_DURATION
  - cognitive_delay returns positive remainder when tool was fast
  - cognitive_delay never returns a negative number
"""

import asyncio
import time
import pytest

# ── The modules under test (do NOT exist yet — all tests are RED) ────────────
from services.voice_agent.interruption import (
    MarkTracker,
    slice_to_confirmed_word,
    prune_conversation_history,
    route_transcript,
    cognitive_delay,
)
from services.voice_agent.vad import ConversationState


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mark_tracker() -> "MarkTracker":
    """Fresh MarkTracker instance for each test."""
    return MarkTracker()


@pytest.fixture
def sample_text() -> str:
    return "Good morning and welcome to Coal Creek Motel how can I help you today"


@pytest.fixture
def multi_turn_history():
    """
    Simulated conversation history: two user turns and one in-progress
    assistant response. The last assistant turn has 12 words total.
    """
    return [
        {"role": "user",      "content": "Hi I'd like to book a room"},
        {"role": "assistant", "content": "Sure I can help you with that"},
        {"role": "user",      "content": "I want a double room"},
        {"role": "assistant", "content": "Great we have double rooms available from Monday"},
    ]


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO 1 — MARK TRACKER: REGISTRATION & CONFIRMATION
# ═══════════════════════════════════════════════════════════════════════════

class TestMarkTrackerRegistration:
    def test_register_word_creates_mark_name(self, mark_tracker):
        """
        register_word(word_index=5) must return a mark name string
        such that confirm_mark can reference it later.
        """
        mark_name = mark_tracker.register_word(5)
        assert isinstance(mark_name, str)
        assert len(mark_name) > 0

    def test_register_word_mark_name_contains_index(self, mark_tracker):
        """
        The mark name for word index 5 must encode the index so Twilio
        can echo it back unambiguously. E.g., 'mark_word_5'.
        """
        mark_name = mark_tracker.register_word(5)
        assert "5" in mark_name

    def test_different_indices_produce_different_marks(self, mark_tracker):
        """Two different word indices must produce two different mark names."""
        mark_a = mark_tracker.register_word(3)
        mark_b = mark_tracker.register_word(7)
        assert mark_a != mark_b

    def test_confirmed_index_starts_at_zero(self, mark_tracker):
        """Before any mark is echoed by Twilio, confirmed_index must be 0."""
        assert mark_tracker.confirmed_index == 0

    def test_confirm_mark_updates_confirmed_index(self, mark_tracker):
        """
        After registering word index 5 and confirming its mark,
        confirmed_index must be updated to 5.
        """
        mark_name = mark_tracker.register_word(5)
        mark_tracker.confirm_mark(mark_name)
        assert mark_tracker.confirmed_index == 5

    def test_confirm_unknown_mark_is_ignored(self, mark_tracker):
        """Confirming a mark that was never registered must not raise and leave index at 0."""
        mark_tracker.confirm_mark("mark_word_99_unknown")
        assert mark_tracker.confirmed_index == 0

    def test_confirm_latest_of_multiple_marks(self, mark_tracker):
        """
        If word indices 3, 7, 11 are registered and marks 3 and 7 are confirmed,
        confirmed_index must be 7 (the most recently confirmed, not highest ever).
        """
        mark_3 = mark_tracker.register_word(3)
        mark_7 = mark_tracker.register_word(7)
        mark_tracker.register_word(11)

        mark_tracker.confirm_mark(mark_3)
        mark_tracker.confirm_mark(mark_7)
        assert mark_tracker.confirmed_index == 7

    def test_reset_clears_confirmed_index(self, mark_tracker):
        """After reset(), confirmed_index must return to 0 and all registrations cleared."""
        mark_name = mark_tracker.register_word(9)
        mark_tracker.confirm_mark(mark_name)
        mark_tracker.reset()
        assert mark_tracker.confirmed_index == 0


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO 1 — SLICE_TO_CONFIRMED_WORD
# ═══════════════════════════════════════════════════════════════════════════

class TestSliceToConfirmedWord:
    def test_zero_confirmed_returns_empty_string(self, sample_text):
        """
        When no marks have been confirmed (confirmed_index=0), the caller
        heard nothing. slice_to_confirmed_word must return an empty string.
        """
        result = slice_to_confirmed_word(sample_text, confirmed_word_index=0)
        assert result == ""

    def test_slice_preserves_first_n_words(self, sample_text):
        """
        confirmed_word_index=3 means words 1, 2, 3 were heard.
        The result must be exactly the first 3 words.
        """
        result = slice_to_confirmed_word(sample_text, confirmed_word_index=3)
        words = sample_text.split()
        expected = " ".join(words[:3])
        assert result == expected

    def test_slice_discards_remainder(self, sample_text):
        """
        Words after confirmed_word_index must NOT appear in the result.
        """
        words = sample_text.split()
        result = slice_to_confirmed_word(sample_text, confirmed_word_index=4)
        result_words = result.split()
        assert result_words == words[:4]
        # Ensure no extra words leaked
        assert len(result_words) == 4

    def test_slice_is_word_boundary_accurate(self, sample_text):
        """
        Slice must cut at whole word boundaries — no partial words.
        """
        result = slice_to_confirmed_word(sample_text, confirmed_word_index=5)
        result_words = result.split()
        original_words = sample_text.split()
        for i, word in enumerate(result_words):
            assert word == original_words[i], f"Word mismatch at position {i}"

    def test_all_words_confirmed_returns_full_text(self, sample_text):
        """
        When confirmed_word_index equals total word count, the full text is returned.
        """
        total_words = len(sample_text.split())
        result = slice_to_confirmed_word(sample_text, confirmed_word_index=total_words)
        assert result == sample_text

    def test_confirmed_index_beyond_length_clamps_to_full_text(self, sample_text):
        """
        If confirmed_word_index exceeds total words (can happen with off-by-one in mark
        registration), the function must clamp and return the full text without raising.
        """
        total_words = len(sample_text.split())
        result = slice_to_confirmed_word(sample_text, confirmed_word_index=total_words + 10)
        assert result == sample_text


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO 1 — CONVERSATION HISTORY PRUNING
# ═══════════════════════════════════════════════════════════════════════════

class TestPruneConversationHistory:
    def test_prune_removes_unheard_words_from_last_assistant_turn(
        self, multi_turn_history
    ):
        """
        The last assistant turn has 8 words. If only 4 were confirmed,
        prune_conversation_history must trim the last assistant message to 4 words.
        """
        pruned = prune_conversation_history(multi_turn_history, confirmed_word_index=4)
        last_assistant = [t for t in pruned if t["role"] == "assistant"][-1]
        result_words = last_assistant["content"].split()
        assert len(result_words) == 4

    def test_prune_preserves_earlier_turns(self, multi_turn_history):
        """
        All turns before the last assistant message must remain unchanged.
        """
        original_first_user = multi_turn_history[0]["content"]
        pruned = prune_conversation_history(multi_turn_history, confirmed_word_index=4)
        assert pruned[0]["content"] == original_first_user

    def test_prune_preserves_all_preceding_assistant_turns(self, multi_turn_history):
        """
        Earlier assistant turns must not be modified during pruning.
        Only the LAST assistant turn is trimmed.
        """
        assistant_turns = [t for t in multi_turn_history if t["role"] == "assistant"]
        pruned = prune_conversation_history(multi_turn_history, confirmed_word_index=4)
        pruned_assistant_turns = [t for t in pruned if t["role"] == "assistant"]

        # First assistant turn must be untouched
        assert pruned_assistant_turns[0]["content"] == assistant_turns[0]["content"]

    def test_prune_zero_confirmed_removes_last_assistant_turn(self, multi_turn_history):
        """
        When confirmed_word_index=0 (nothing was heard), the last assistant
        message must be removed entirely (empty content or removed from list).
        """
        pruned = prune_conversation_history(multi_turn_history, confirmed_word_index=0)
        last_assistant = [t for t in pruned if t["role"] == "assistant"][-1]
        # The last assistant turn should be the PREVIOUS one (unchanged)
        # because the current one was fully pruned (nothing heard)
        assert last_assistant["content"] == "Sure I can help you with that"

    def test_prune_with_no_assistant_turn_returns_unchanged(self):
        """
        If the history has no assistant turns, prune must return it unchanged.
        """
        history = [
            {"role": "user", "content": "Hello there"},
            {"role": "user", "content": "Anyone there"},
        ]
        pruned = prune_conversation_history(history, confirmed_word_index=5)
        assert pruned == history

    def test_prune_with_empty_history_returns_empty(self):
        """Pruning an empty history must return an empty list without raising."""
        pruned = prune_conversation_history([], confirmed_word_index=5)
        assert pruned == []

    def test_prune_rounds_back_to_last_sentence_boundary(self):
        """
        DELTA-3 (Research §4): Word-level pruning is fragile under telephony ASR errors.
        When confirmed words end mid-sentence, prune_conversation_history must round
        back to the last complete sentence boundary (., !, ?) to prevent the LLM
        from having a sentence fragment in its memory.

        Setup: Last assistant turn has 3 sentences. Confirmed words cut mid-3rd sentence.
        Expected: Prune retains sentences 1+2 only (complete sentences).
        """
        history = [
            {"role": "user", "content": "Do you have rooms?"},
            {
                "role": "assistant",
                "content": (
                    "Hello there. I can help you with that. "
                    "We have rooms available from Monday."
                ),
            },
        ]
        # Word 11 lands mid-way through the 3rd sentence ("We have rooms available")
        # The 3rd sentence starts at approximately word 10
        pruned = prune_conversation_history(history, confirmed_word_index=11)
        last_assistant = [t for t in pruned if t["role"] == "assistant"][-1]

        # Must end at a complete sentence boundary
        assert last_assistant["content"].strip().endswith("."), (
            f"Expected sentence-boundary prune, got: '{last_assistant['content']}'"
        )
        # Must NOT contain the fragment mid-sentence of the third sentence
        assert "We have rooms" not in last_assistant["content"], (
            "Mid-sentence fragment must not appear in pruned LLM history"
        )


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO 2 — STATE-AWARE TRANSCRIPT ROUTING
# ═══════════════════════════════════════════════════════════════════════════

class TestRouteTranscript:
    def test_backchannel_during_agent_speaking_is_ignored(self):
        """
        While AGENT_SPEAKING, a 1-word backchannel ('okay') must route to 'ignore'.
        The agent must not be interrupted.
        """
        action = route_transcript("okay", state=ConversationState.AGENT_SPEAKING)
        assert action == "ignore"

    def test_three_word_backchannel_during_agent_speaking_is_ignored(self):
        """
        While AGENT_SPEAKING, a 3-word backchannel ('yeah sure okay') must route to 'ignore'.
        """
        action = route_transcript("yeah sure okay", state=ConversationState.AGENT_SPEAKING)
        assert action == "ignore"

    def test_trigger_word_during_agent_speaking_is_interrupt(self):
        """
        While AGENT_SPEAKING, 'wait' (a trigger word) must route to 'interrupt'
        even though it is only 1 word.
        """
        action = route_transcript("wait", state=ConversationState.AGENT_SPEAKING)
        assert action == "interrupt"

    def test_long_utterance_during_agent_speaking_is_interrupt(self):
        """
        While AGENT_SPEAKING, an utterance of >3 words must route to 'interrupt'.
        """
        action = route_transcript(
            "actually I want to change my booking",
            state=ConversationState.AGENT_SPEAKING
        )
        assert action == "interrupt"

    def test_single_yes_during_awaiting_input_is_forward(self):
        """
        While AWAITING_INPUT, 'yes' (1 word that would normally be a backchannel)
        must route to 'forward' — the agent asked a confirmation question.
        """
        action = route_transcript("yes", state=ConversationState.AWAITING_INPUT)
        assert action == "forward"

    def test_single_sure_during_awaiting_input_is_forward(self):
        """
        While AWAITING_INPUT, 'sure' must route to 'forward', not 'ignore'.
        """
        action = route_transcript("sure", state=ConversationState.AWAITING_INPUT)
        assert action == "forward"

    def test_long_utterance_during_awaiting_input_is_forward(self):
        """
        While AWAITING_INPUT, any utterance (short or long) must route to 'forward'.
        """
        action = route_transcript(
            "I would like to book from Monday to Wednesday please",
            state=ConversationState.AWAITING_INPUT
        )
        assert action == "forward"

    def test_empty_transcript_during_awaiting_input_is_ignore(self):
        """
        An empty transcript (noise/silence artifact) must always route to 'ignore'
        regardless of state, to avoid triggering an LLM call with no content.
        """
        action = route_transcript("", state=ConversationState.AWAITING_INPUT)
        assert action == "ignore"

    def test_empty_transcript_during_agent_speaking_is_ignore(self):
        """An empty transcript must be ignored in all states."""
        action = route_transcript("", state=ConversationState.AGENT_SPEAKING)
        assert action == "ignore"


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO 4 — COGNITIVE DELAY CALCULATION
# ═══════════════════════════════════════════════════════════════════════════

class TestCognitiveDelay:
    """
    Research-grounded spec (Perplexity Handbook §8, DELTA-1):

    cognitive_delay(elapsed_s) returns milliseconds to pause as a PERCEPTION CUE
    before TTS starts on tool-call responses. It is NOT a minimum-duration floor.

    Rules:
      - Fast tool call (< ~200ms): return ~120ms thinking cue (±40ms variance allowed)
      - Slow tool call (>= ~200ms): return 0 — natural pacing already present
      - Returned value is in MILLISECONDS (not seconds)
      - Hard ceiling: NEVER return > 300ms (over 300ms feels broken per research)
      - Never return negative

    Config target: COGNITIVE_THINKING_CUE_MS = 120, MAX_COGNITIVE_CUE_MS = 300
    """

    def test_fast_tool_call_gets_thinking_cue(self):
        """
        Tool call took 0.05s (very fast, cache hit) → return ~120ms thinking cue.
        The cue makes the response feel considered, not robotic.
        Accepts 80–160ms range to accommodate ±40ms variance.
        """
        delay_ms = cognitive_delay(elapsed_s=0.05)
        assert 80 <= delay_ms <= 160, (
            f"Expected ~120ms thinking cue for fast lookup, got {delay_ms}ms"
        )

    def test_slow_tool_call_gets_no_extra_delay(self):
        """
        Tool call took 0.8s (slow DB query) → return 0ms.
        The natural latency already provides pacing; adding cue would feel broken.
        """
        delay_ms = cognitive_delay(elapsed_s=0.8)
        assert delay_ms == 0, (
            f"Expected 0 extra delay for slow tool call, got {delay_ms}ms"
        )

    def test_cue_never_exceeds_300ms_ceiling(self):
        """
        Per research: >300ms feels sluggish/broken. The hard ceiling must hold
        regardless of how fast the tool call was (including instant/0ms).
        """
        for elapsed in [0.0, 0.01, 0.05, 0.1]:
            delay_ms = cognitive_delay(elapsed_s=elapsed)
            assert delay_ms <= 300, (
                f"Delay {delay_ms}ms exceeds 300ms ceiling for elapsed={elapsed}s"
            )

    def test_delay_never_negative(self):
        """
        For any elapsed time, cognitive_delay must never return a negative number.
        """
        for elapsed in [0.0, 0.05, 0.2, 0.5, 1.0, 2.0, 5.0]:
            delay_ms = cognitive_delay(elapsed_s=elapsed)
            assert delay_ms >= 0, (
                f"Negative delay {delay_ms}ms returned for elapsed={elapsed}s"
            )

    def test_returns_integer_or_float_milliseconds(self):
        """
        Return type must be numeric (int or float) representing milliseconds.
        This is NOT seconds — the caller sleeps with asyncio.sleep(delay_ms / 1000).
        """
        delay_ms = cognitive_delay(elapsed_s=0.05)
        assert isinstance(delay_ms, (int, float))
        # Sanity check: if it were seconds, this would be ~0.12 which is < 1
        # If it's correctly ms, it should be >= 80
        assert delay_ms >= 80, (
            f"Value {delay_ms} looks like seconds not milliseconds — expected >= 80ms"
        )
