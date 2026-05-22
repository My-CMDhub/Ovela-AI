"""
Tests for Conversational Hardening — Interruption Trimming.

Verifies the mathematical word-count pruning of assistant transcript
when the user interrupts mid-sentence (VAD fires before TTS finishes).

Formula: words_spoken = floor(elapsed_seconds * wpm / 60)
"""
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# trim_assistant_transcript — pure function tests
# ─────────────────────────────────────────────────────────────────────────────

def test_trim_returns_words_spoken_at_150wpm():
    """2 seconds at 150 WPM = 5 words spoken → trim to first 5 words."""
    from services.voice_agent.handler import trim_assistant_transcript
    text = "Sure, I can help you book a queen room for tomorrow. Let me check availability."
    result = trim_assistant_transcript(text, elapsed_seconds=2.0, wpm=150)
    assert result == "Sure, I can help you"


def test_trim_zero_elapsed_returns_empty():
    """0 seconds elapsed → caller heard nothing → return empty string."""
    from services.voice_agent.handler import trim_assistant_transcript
    result = trim_assistant_transcript("Hello there!", elapsed_seconds=0.0)
    assert result == ""


def test_trim_elapsed_covers_full_text_returns_full():
    """Elapsed is long enough to cover all words → return full text unchanged."""
    from services.voice_agent.handler import trim_assistant_transcript
    text = "Great, let me check that for you."  # 7 words
    # 7 words at 150 WPM = 2.8s needed. Give 5s → full text returned.
    result = trim_assistant_transcript(text, elapsed_seconds=5.0, wpm=150)
    assert result == text


def test_trim_single_word_partial():
    """Very fast interruption (0.3s) → 0 full words → empty string."""
    from services.voice_agent.handler import trim_assistant_transcript
    result = trim_assistant_transcript("Sure thing.", elapsed_seconds=0.3, wpm=150)
    # 0.3 * 150 / 60 = 0.75 → floor = 0 words
    assert result == ""


def test_trim_exactly_one_word():
    """0.4 seconds at 150 WPM = 1 word heard."""
    from services.voice_agent.handler import trim_assistant_transcript
    result = trim_assistant_transcript("Sure thing happened today.", elapsed_seconds=0.4, wpm=150)
    # 0.4 * 150 / 60 = 1.0 → floor = 1 word
    assert result == "Sure"


def test_trim_handles_empty_input():
    """Empty or whitespace text → return empty string."""
    from services.voice_agent.handler import trim_assistant_transcript
    assert trim_assistant_transcript("", elapsed_seconds=2.0) == ""
    assert trim_assistant_transcript("   ", elapsed_seconds=2.0) == ""


def test_trim_custom_wpm():
    """Custom WPM respected — 120 WPM instead of default 150."""
    from services.voice_agent.handler import trim_assistant_transcript
    text = "One two three four five six seven eight."
    # 3s at 120 WPM = 6 words
    result = trim_assistant_transcript(text, elapsed_seconds=3.0, wpm=120)
    assert result == "One two three four five six"


def test_trim_negative_elapsed_returns_empty():
    """Negative elapsed (clock skew edge case) → return empty, never crash."""
    from services.voice_agent.handler import trim_assistant_transcript
    result = trim_assistant_transcript("Hello there!", elapsed_seconds=-1.0)
    assert result == ""
