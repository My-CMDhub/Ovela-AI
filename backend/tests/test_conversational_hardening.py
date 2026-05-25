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


# ─────────────────────────────────────────────────────────────────────────────
# Task 4.2: Interruption System Tags tests
# ─────────────────────────────────────────────────────────────────────────────

def test_system_note_stripped_from_tts():
    """Ensure [System Note: ...] is stripped from TTS output."""
    from services.voice_agent.text_utils import clean_tts_output
    text = "Sure, I can help. [System Note: Caller interrupted. Continue from last confirmed point.] What dates?"
    result = clean_tts_output(text)
    assert result == "Sure, I can help. What dates?"

@pytest.mark.asyncio
async def test_vad_interruption_injects_system_note():
    """Ensure a VAD interruption injects a System Note into Deepgram context."""
    from services.voice_agent.handler import VoiceAgentHandler
    from services.voice_agent.latency_tracker import LatencyTracker
    import json
    from unittest.mock import MagicMock, AsyncMock, patch
    
    # Mock latency tracker and silence monitor
    latency_mock = MagicMock(spec=LatencyTracker)
    silence_monitor_mock = MagicMock()
    
    # Instantiate handler
    handler = VoiceAgentHandler(None)
    handler.call_sid = "test_call_sid"
    handler.stream_sid = "test_stream_sid"
    handler.latency = latency_mock
    handler.silence_monitor = silence_monitor_mock
    
    # Mock Deepgram and Twilio WebSockets
    handler.deepgram_ws = AsyncMock()
    handler.twilio_ws = AsyncMock()
    
    # Set up interruption scenario: AI was speaking
    handler._ai_is_speaking = True
    handler._tts_playback_start = 1000.0  # past time
    handler.transcript = [{"role": "ai", "text": "I can definitely help with that booking right now."}]
    
    # Mock time.time to be later
    with patch('time.time', return_value=1002.0):
        # Fire user started speaking
        await handler._handle_user_started_speaking()
    
    # Verify the Twilio 'clear' was sent
    handler.twilio_ws.send_json.assert_called_once_with({
        "event": "clear",
        "streamSid": "test_stream_sid"
    })
    
    # Verify Deepgram was injected with the system note
    expected_msg = {
        "type": "InjectUserMessage",
        "content": "[System Note: Caller interrupted. Continue from last confirmed point.]"
    }
    handler.deepgram_ws.send.assert_called_once()
    sent_call = handler.deepgram_ws.send.call_args[0][0]
    assert json.loads(sent_call) == expected_msg
