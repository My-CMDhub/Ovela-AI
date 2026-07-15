"""
tests/test_vad.py
=================
Phase 12.1 — RED-state failing unit tests for the VAD module.

These tests are written BEFORE the implementation module
(services/voice_agent/vad.py) exists. Every test MUST fail with
ImportError or AssertionError until GREEN is reached.

Scenarios covered:
  - mu-law → PCM16 decoding accuracy (audioop-lts compatibility)
  - Valid frame size computation for 8 kHz at 10 / 20 / 30ms windows
  - Invalid frame duration guard (webrtcvad only accepts 10/20/30ms)
  - VadProcessor construction & aggressiveness 0–3
  - VadProcessor.is_speech classification on PCM frames
  - VadProcessor.process_mulaw end-to-end (mu-law → decode → classify)
  - Immunity window: speech suppressed inside 500ms, captured after expiry
  - Backchannel word-count filter: ≤3 words ignored while AGENT_SPEAKING
  - Backchannel trigger words ('wait', 'stop') override word-count filter
  - ConversationState enum distinctness and state-aware routing contract
"""

import audioop
import time
import struct
import math
import pytest

# ── The module under test (does NOT exist yet — all tests are RED) ──────────
from services.voice_agent.vad import (
    VadProcessor,
    ConversationState,
    decode_mulaw_to_pcm16,
    compute_frame_bytes,
    is_backchannel_word,
)


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def silence_mulaw_frame_20ms() -> bytes:
    """
    160 bytes of mu-law encoded silence (zero PCM → mu-law 0xFF).
    Twilio streams 8 kHz mu-law at 160 bytes per 20ms packet.
    """
    return bytes([0xFF] * 160)


@pytest.fixture
def speech_pcm16_frame_20ms() -> bytes:
    """
    320 bytes of synthetic 8 kHz PCM16 speech-like signal (400 Hz sine).
    Used to verify webrtcvad accepts and classifies the correctly-shaped buffer.
    """
    samples = 160  # 8000 Hz × 0.020 s = 160 samples
    frame = bytearray()
    for i in range(samples):
        val = int(16000 * math.sin(2 * math.pi * 400 * i / 8000))
        frame += struct.pack("<h", val)
    return bytes(frame)


@pytest.fixture
def silence_pcm16_frame_20ms() -> bytes:
    """320 bytes of pure digital silence (all zeros, PCM16 at 8 kHz)."""
    return bytes(320)


@pytest.fixture
def vad_processor() -> "VadProcessor":
    """VadProcessor at aggressiveness=3 (production default)."""
    return VadProcessor(aggressiveness=3, sample_rate=8000, frame_ms=20)


# ═══════════════════════════════════════════════════════════════════════════
# 1. MU-LAW DECODING
# ═══════════════════════════════════════════════════════════════════════════

class TestMulawDecoding:
    def test_decode_returns_bytes(self, silence_mulaw_frame_20ms):
        """decode_mulaw_to_pcm16 must return a bytes object."""
        result = decode_mulaw_to_pcm16(silence_mulaw_frame_20ms)
        assert isinstance(result, bytes)

    def test_decode_doubles_byte_length(self, silence_mulaw_frame_20ms):
        """mu-law is 8-bit; PCM16 is 16-bit. 160 bytes → 320 bytes."""
        result = decode_mulaw_to_pcm16(silence_mulaw_frame_20ms)
        assert len(result) == len(silence_mulaw_frame_20ms) * 2

    def test_decode_silence_is_near_zero(self, silence_mulaw_frame_20ms):
        """Decoded mu-law silence (0xFF) must map to PCM values near zero [-100, 100]."""
        pcm = decode_mulaw_to_pcm16(silence_mulaw_frame_20ms)
        samples = struct.unpack(f"<{len(pcm)//2}h", pcm)
        assert all(abs(s) <= 100 for s in samples), (
            f"Silence decode produced out-of-range samples: max={max(abs(s) for s in samples)}"
        )

    def test_decode_matches_audioop_ulaw2lin(self, silence_mulaw_frame_20ms):
        """decode_mulaw_to_pcm16 must produce byte-identical output to audioop.ulaw2lin."""
        expected = audioop.ulaw2lin(silence_mulaw_frame_20ms, 2)
        result = decode_mulaw_to_pcm16(silence_mulaw_frame_20ms)
        assert result == expected


# ═══════════════════════════════════════════════════════════════════════════
# 2. FRAME SIZE COMPUTATION
# ═══════════════════════════════════════════════════════════════════════════

class TestFrameSizeComputation:
    def test_20ms_frame_is_320_bytes_pcm16(self):
        """8000 Hz × 20ms = 160 samples × 2 bytes = 320 bytes."""
        assert compute_frame_bytes(sample_rate=8000, frame_ms=20) == 320

    def test_30ms_frame_is_480_bytes_pcm16(self):
        """8000 Hz × 30ms = 240 samples × 2 bytes = 480 bytes."""
        assert compute_frame_bytes(sample_rate=8000, frame_ms=30) == 480

    def test_10ms_frame_is_160_bytes_pcm16(self):
        """8000 Hz × 10ms = 80 samples × 2 bytes = 160 bytes."""
        assert compute_frame_bytes(sample_rate=8000, frame_ms=10) == 160

    def test_invalid_frame_duration_raises(self):
        """webrtcvad only accepts 10, 20, or 30ms frames; 25ms must raise ValueError."""
        with pytest.raises(ValueError, match="frame_ms"):
            compute_frame_bytes(sample_rate=8000, frame_ms=25)


# ═══════════════════════════════════════════════════════════════════════════
# 3. VAD PROCESSOR CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════

class TestVadProcessorConstruction:
    def test_default_aggressiveness_is_three(self):
        """Production default aggressiveness level must be 3."""
        vp = VadProcessor(aggressiveness=3, sample_rate=8000, frame_ms=20)
        assert vp.aggressiveness == 3

    @pytest.mark.parametrize("level", [0, 1, 2, 3])
    def test_valid_aggressiveness_levels_accepted(self, level):
        """All four valid webrtcvad aggressiveness levels (0–3) must construct cleanly."""
        vp = VadProcessor(aggressiveness=level, sample_rate=8000, frame_ms=20)
        assert vp.aggressiveness == level

    def test_invalid_aggressiveness_raises(self):
        """Aggressiveness level 4+ must raise ValueError."""
        with pytest.raises(ValueError, match="aggressiveness"):
            VadProcessor(aggressiveness=4, sample_rate=8000, frame_ms=20)

    def test_sample_rate_stored(self):
        """VadProcessor must store sample_rate for downstream frame sizing."""
        vp = VadProcessor(aggressiveness=3, sample_rate=8000, frame_ms=20)
        assert vp.sample_rate == 8000

    def test_frame_ms_stored(self):
        """VadProcessor must store frame_ms for downstream frame sizing."""
        vp = VadProcessor(aggressiveness=3, sample_rate=8000, frame_ms=20)
        assert vp.frame_ms == 20


# ═══════════════════════════════════════════════════════════════════════════
# 4. VAD SPEECH CLASSIFICATION (PCM frames)
# ═══════════════════════════════════════════════════════════════════════════

class TestVadSpeechClassification:
    def test_silence_frame_is_not_speech(self, vad_processor, silence_pcm16_frame_20ms):
        """A 320-byte all-zero PCM16 frame at 8 kHz must NOT be classified as speech."""
        result = vad_processor.is_speech(silence_pcm16_frame_20ms)
        assert result is False

    def test_speech_frame_is_classified_as_speech(self, vad_processor, speech_pcm16_frame_20ms):
        """A 400 Hz sine wave PCM16 frame at aggressiveness=3 must be classified as speech."""
        result = vad_processor.is_speech(speech_pcm16_frame_20ms)
        assert result is True

    def test_wrong_frame_size_raises(self, vad_processor):
        """Passing a frame that is not exactly 320 bytes (20ms at 8kHz) must raise ValueError."""
        with pytest.raises(ValueError, match="frame size"):
            vad_processor.is_speech(bytes(100))

    def test_mulaw_input_raises_on_wrong_size(self, vad_processor, silence_mulaw_frame_20ms):
        """
        Raw mu-law frame (160 bytes) is the wrong size for is_speech (expects 320 bytes).
        Must raise ValueError to guard against callers forgetting to decode first.
        """
        with pytest.raises(ValueError, match="frame size"):
            vad_processor.is_speech(silence_mulaw_frame_20ms)


# ═══════════════════════════════════════════════════════════════════════════
# 5. VAD PROCESSOR — MU-LAW END-TO-END (process_mulaw)
# ═══════════════════════════════════════════════════════════════════════════

class TestVadProcessorMulawEndToEnd:
    def test_process_mulaw_returns_bool(self, vad_processor, silence_mulaw_frame_20ms):
        """
        VadProcessor.process_mulaw must accept raw Twilio mu-law bytes,
        decode internally, and return a boolean classification.
        """
        result = vad_processor.process_mulaw(silence_mulaw_frame_20ms)
        assert isinstance(result, bool)

    def test_process_mulaw_silence_is_false(self, vad_processor, silence_mulaw_frame_20ms):
        """Silence mu-law → decoded PCM → False (not speech)."""
        result = vad_processor.process_mulaw(silence_mulaw_frame_20ms)
        assert result is False

    def test_process_mulaw_wrong_size_raises(self, vad_processor):
        """
        process_mulaw of 80-byte frame (not valid 20ms mu-law) must raise ValueError.
        Twilio always sends exactly 160-byte packets; anything else is malformed.
        """
        with pytest.raises(ValueError, match="mu-law frame"):
            vad_processor.process_mulaw(bytes(80))


# ═══════════════════════════════════════════════════════════════════════════
# 6. IMMUNITY WINDOW
# ═══════════════════════════════════════════════════════════════════════════

class TestImmunityWindow:
    def test_speech_during_immunity_is_suppressed(self, vad_processor):
        """
        After arming the 500ms immunity window, a speech event 50ms later
        must return is_immune=True (interruption suppressed).
        """
        vad_processor.arm_immunity(duration_s=0.5)
        time.sleep(0.05)  # 50ms inside the window
        assert vad_processor.is_immune() is True

    def test_speech_after_immunity_is_captured(self, vad_processor):
        """
        After the window expires, is_immune must return False.
        Uses 10ms window so the test completes quickly.
        """
        vad_processor.arm_immunity(duration_s=0.010)
        time.sleep(0.015)  # wait for expiry
        assert vad_processor.is_immune() is False

    def test_immunity_not_armed_by_default(self, vad_processor):
        """VadProcessor starts with no active immunity window."""
        assert vad_processor.is_immune() is False

    def test_arm_immunity_sets_future_expiry(self, vad_processor):
        """arm_immunity must set an internal expiry timestamp in the future."""
        before = time.time()
        vad_processor.arm_immunity(duration_s=0.5)
        assert vad_processor._immunity_until > before


# ═══════════════════════════════════════════════════════════════════════════
# 7. BACKCHANNEL WORD FILTER
# ═══════════════════════════════════════════════════════════════════════════

class TestBackchannelWordFilter:
    @pytest.mark.parametrize("utterance", [
        "hmm",
        "okay",
        "yeah",
        "sure",
        "right okay",
        "yeah sure okay",   # exactly 3 words
    ])
    def test_short_utterance_is_backchannel(self, utterance):
        """Utterances of ≤3 words must be classified as backchannels (ignored while speaking)."""
        assert is_backchannel_word(utterance) is True

    @pytest.mark.parametrize("utterance", [
        "wait stop that is wrong",
        "actually I want to book next Wednesday instead",
        "yes I would like to confirm the booking now",
    ])
    def test_long_utterance_is_not_backchannel(self, utterance):
        """Utterances of >3 words must NOT be classified as backchannels."""
        assert is_backchannel_word(utterance) is False

    def test_empty_string_is_backchannel(self):
        """An empty transcript (noise artifact) must be treated as a backchannel."""
        assert is_backchannel_word("") is True

    def test_trigger_word_wait_is_not_backchannel(self):
        """
        'wait' is a defined trigger word and must NOT be ignored,
        even though it is 1 word. It signals genuine correction intent.
        """
        assert is_backchannel_word("wait") is False

    def test_trigger_word_stop_is_not_backchannel(self):
        """'stop' must always trigger interruption regardless of word count."""
        assert is_backchannel_word("stop") is False

    def test_negation_word_no_is_not_backchannel(self):
        """
        DELTA-5 (Research §5): 'no' is a negation word and must NOT be treated
        as a backchannel even though it is 1 word. Research explicitly lists
        negation words as override signals for genuine corrections.
        """
        assert is_backchannel_word("no") is False

    def test_correction_word_actually_is_not_backchannel(self):
        """
        DELTA-5 (Research §5): 'actually' is a self-correction marker and must
        NOT be treated as a backchannel. It signals the user is about to correct
        themselves or redirect the conversation.
        """
        assert is_backchannel_word("actually") is False


# ═══════════════════════════════════════════════════════════════════════════
# 8. CONVERSATION STATE ENUM
# ═══════════════════════════════════════════════════════════════════════════

class TestConversationState:
    def test_agent_speaking_state_exists(self):
        """ConversationState.AGENT_SPEAKING must be a valid enum member."""
        assert ConversationState.AGENT_SPEAKING is not None

    def test_awaiting_input_state_exists(self):
        """ConversationState.AWAITING_INPUT must be a valid enum member."""
        assert ConversationState.AWAITING_INPUT is not None

    def test_states_are_distinct(self):
        """AGENT_SPEAKING and AWAITING_INPUT must be different enum values."""
        assert ConversationState.AGENT_SPEAKING != ConversationState.AWAITING_INPUT

    def test_awaiting_input_contract_for_single_word_yes(self):
        """
        CONTRACT TEST — Scenario 2 state-aware routing.

        'yes' (1 word) IS classified as a backchannel by is_backchannel_word.
        The orchestrator is responsible for skipping the backchannel filter
        when state == AWAITING_INPUT. This test documents that contract.
        """
        # The filter itself says 'yes' is a backchannel (1 word, no trigger words)
        assert is_backchannel_word("yes") is True
        # The ConversationState enum exists so orchestrators can key off it
        assert ConversationState.AWAITING_INPUT is not None
        assert ConversationState.AGENT_SPEAKING is not None
