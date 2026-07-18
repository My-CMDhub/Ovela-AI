"""
services/voice_agent/vad.py
===========================
Phase 12.1 — Local Voice Activity Detection (VAD) module using webrtcvad.

Provides ultra-low latency frame-level voice activity detection on telephony
8kHz mu-law / PCM16 streams to enable sub-40ms barge-in and precise turn-taking
in the cascaded streaming pipeline.
"""

import time
import math
import audioop
from enum import Enum
from typing import Optional
import webrtcvad


class ConversationState(Enum):
    """
    State of the conversation for state-aware VAD and backchannel routing.
    """
    AGENT_SPEAKING = "AGENT_SPEAKING"
    AWAITING_INPUT = "AWAITING_INPUT"


def decode_mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """
    Decode 8-bit mu-law telephony bytes to 16-bit linear PCM bytes using audioop.
    
    Args:
        mulaw_bytes: Raw mu-law audio payload from Twilio Media Streams.
        
    Returns:
        Decoded 16-bit little-endian PCM bytes (twice the length of input).
    """
    return audioop.ulaw2lin(mulaw_bytes, 2)


def compute_frame_bytes(sample_rate: int, frame_ms: int) -> int:
    """
    Compute expected byte size of a 16-bit PCM frame for a given duration.
    
    webrtcvad strictly requires frames of 10ms, 20ms, or 30ms duration.
    
    Args:
        sample_rate: Audio sampling rate in Hz (e.g., 8000 for telephony).
        frame_ms: Frame duration in milliseconds (must be 10, 20, or 30).
        
    Returns:
        Number of bytes expected for a PCM16 frame.
        
    Raises:
        ValueError: If frame_ms is not 10, 20, or 30.
    """
    if frame_ms not in (10, 20, 30):
        raise ValueError(f"Invalid frame_ms: {frame_ms}. webrtcvad only supports 10, 20, or 30ms frames.")
    return int(sample_rate * (frame_ms / 1000) * 2)


class VadProcessor:
    """
    Wraps webrtcvad with telephony mu-law support, strict frame sizing,
    and self-echo immunity window management.
    """
    def __init__(self, aggressiveness: int = 3, sample_rate: int = 8000, frame_ms: int = 20):
        """
        Initialize the VAD processor.
        
        Args:
            aggressiveness: VAD sensitivity level 0-3 (3 is most aggressive in filtering noise).
            sample_rate: Audio sampling rate in Hz (must be 8000, 16000, 32000, or 48000).
            frame_ms: Frame duration in milliseconds (must be 10, 20, or 30).
            
        Raises:
            ValueError: If aggressiveness or frame_ms are out of valid bounds.
        """
        if not (0 <= aggressiveness <= 3):
            raise ValueError(f"Invalid aggressiveness: {aggressiveness}. Must be between 0 and 3.")
            
        self.aggressiveness = aggressiveness
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        
        # Validate frame size and store expected byte lengths
        self._expected_pcm_bytes = compute_frame_bytes(sample_rate, frame_ms)
        self._expected_mulaw_bytes = self._expected_pcm_bytes // 2
        
        self._vad = webrtcvad.Vad(aggressiveness)
        self._immunity_until: float = 0.0
        self.gate_open = False
        self.silence_start_time = None

    def calculate_dbfs(self, pcm_frame: bytes) -> float:
        """
        Compute standard Root Mean Square (RMS) from a 16-bit PCM buffer
        and convert it to logarithmic Decibels Relative to Full Scale (dBFS).
        Reference 32768 for maximum signed 16-bit scale value.
        """
        rms_val = audioop.rms(pcm_frame, 2)
        if rms_val <= 0:
            return -96.0
        dbfs = 20 * math.log10(rms_val / 32768.0)
        return dbfs

    def is_speech(self, pcm_frame: bytes) -> bool:
        """
        Classify a 16-bit PCM audio frame as speech or non-speech.
        
        Args:
            pcm_frame: Raw 16-bit PCM audio frame.
            
        Returns:
            True if voice activity is detected, False otherwise.
            
        Raises:
            ValueError: If pcm_frame size does not exactly match the configured frame_ms.
        """
        if len(pcm_frame) != self._expected_pcm_bytes:
            raise ValueError(
                f"Invalid PCM frame size: {len(pcm_frame)} bytes. Expected {self._expected_pcm_bytes} bytes for {self.frame_ms}ms at {self.sample_rate}Hz."
            )
        
        # Convert RMS to dBFS and run Dynamic Adaptive Hysteresis
        dbfs = self.calculate_dbfs(pcm_frame)
        
        UPPER_GATE_DBFS = -32.0
        LOWER_FLOOR_DBFS = -45.0
        HANGTIME_S = 0.150
        
        current_time = time.time()
        
        if dbfs > UPPER_GATE_DBFS:
            self.gate_open = True
            self.silence_start_time = None
        elif dbfs < LOWER_FLOOR_DBFS:
            if self.gate_open:
                if self.silence_start_time is None:
                    self.silence_start_time = current_time
                elif current_time - self.silence_start_time >= HANGTIME_S:
                    self.gate_open = False
        else: # LOWER_FLOOR_DBFS <= dbfs <= UPPER_GATE_DBFS
            if self.gate_open:
                self.silence_start_time = None

        if not self.gate_open:
            return False
            
        return self._vad.is_speech(pcm_frame, self.sample_rate)

    def process_mulaw(self, mulaw_frame: bytes) -> bool:
        """
        Decode and classify a raw mu-law audio packet as speech or non-speech.
        
        Args:
            mulaw_frame: Raw mu-law packet from Twilio Media Streams.
            
        Returns:
            True if voice activity is detected, False otherwise.
            
        Raises:
            ValueError: If mulaw_frame size does not match expected mu-law byte size.
        """
        if len(mulaw_frame) != self._expected_mulaw_bytes:
            raise ValueError(
                f"Invalid mu-law frame size: {len(mulaw_frame)} bytes. Expected {self._expected_mulaw_bytes} bytes for {self.frame_ms}ms at {self.sample_rate}Hz."
            )
        pcm_frame = decode_mulaw_to_pcm16(mulaw_frame)
        return self.is_speech(pcm_frame)

    def arm_immunity(self, duration_s: float = 0.5) -> None:
        """
        Arm the echo immunity window for a specified duration.
        
        During this window, any detected speech should be treated as self-echo
        and suppressed by calling is_immune().
        
        Args:
            duration_s: Duration in seconds for which immunity remains active.
        """
        self._immunity_until = time.time() + duration_s

    def is_immune(self) -> bool:
        """
        Check if the echo immunity window is currently active.
        
        Returns:
            True if the current timestamp is within the immunity duration, False otherwise.
        """
        return time.time() < self._immunity_until


def is_backchannel_word(utterance: str) -> bool:
    """
    Determine if an utterance is a short affirmation backchannel (≤3 words)
    that should be ignored while the AI is speaking, or a genuine correction/interruption.
    
    Trigger override words ('wait', 'stop', 'no', 'actually') are never treated
    as backchannels even if <=3 words.
    
    Args:
        utterance: Transcribed text snippet or user utterance.
        
    Returns:
        True if the utterance is classified as a backchannel, False otherwise.
    """
    if not utterance or not utterance.strip():
        return True
        
    # Lowercase and strip basic punctuation for word count and trigger checks
    normalized = utterance.lower()
    for char in ".,!?:;()-":
        normalized = normalized.replace(char, " ")
    words = normalized.split()
    
    if not words:
        return True
        
    # Trigger words that must immediately override the backchannel filter
    trigger_words = {"wait", "stop", "no", "actually"}
    if any(w in trigger_words for w in words):
        return False
        
    return len(words) <= 3
