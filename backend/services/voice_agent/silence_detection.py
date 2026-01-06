"""
Voice Agent Silence Detection Module.

Monitors for extended silence during calls and triggers appropriate prompts
or call termination based on configurable thresholds.
"""

import asyncio
import logging
import time
import random

from .config import (
    SOFT_SILENCE_THRESHOLD,
    HARD_SILENCE_THRESHOLD,
    ABANDON_THRESHOLD,
    THINKING_PATTERNS,
    get_random_silence_prompt,
)

logger = logging.getLogger(__name__)


class SilenceMonitor:
    """
    Monitors for extended silence and triggers prompts or call end.
    
    Thresholds:
    - SOFT_SILENCE_THRESHOLD (10s): First gentle check-in
    - HARD_SILENCE_THRESHOLD (20s): More urgent check
    - ABANDON_THRESHOLD (25s): End call politely
    """
    
    def __init__(self):
        self.last_user_speech_time = None
        self.silence_followup_sent = False
        self.silence_followup_count = 0
        self.silence_check_start_time = None
        self.silence_check_id = 0  # Counter to invalidate old checks
        self.last_ai_message = ""
        self.ai_asked_question = False
    
    def on_user_speech(self):
        """Called when user starts speaking - resets silence tracking."""
        self.last_user_speech_time = time.time()
        self.silence_followup_sent = False
        self.silence_followup_count = 0
    
    def on_ai_finished_speaking(self, message: str = ""):
        """
        Called when AI finishes speaking - starts silence timer.
        
        Args:
            message: The AI's last message (for context-aware timing)
        """
        # Estimate TTS playback time (about 12-15 characters per second for natural speech)
        # This accounts for the delay between Deepgram sending audio and Twilio finishing playback
        estimated_tts_seconds = len(message) / 12 if message else 0
        self.tts_buffer = min(estimated_tts_seconds, 15)  # Cap at 15 seconds
        
        # Add TTS buffer to start time (silence timer starts after TTS finishes)
        self.silence_check_start_time = time.time() + self.tts_buffer
        self.silence_check_id += 1  # Invalidate any running checks
        self.last_ai_message = message
        self.ai_asked_question = self._requires_thinking(message)
        
        # CRITICAL FIX: Reset followup count so new silence detection cycle can trigger
        self.silence_followup_count = 0
        self.silence_followup_sent = False
        
        if self.tts_buffer > 2:
            logger.debug(f"⏱️ Added {self.tts_buffer:.1f}s TTS buffer for {len(message)} char message")
    
    def _requires_thinking(self, message: str) -> bool:
        """Check if the AI's message requires user to think (longer threshold)."""
        message_lower = message.lower()
        return any(pattern in message_lower for pattern in THINKING_PATTERNS)
    
    def get_check_id(self) -> int:
        """Get current check ID for validation."""
        return self.silence_check_id
    
    def is_check_valid(self, check_id: int) -> bool:
        """Check if a silence check is still valid (no new AI speech started)."""
        return check_id == self.silence_check_id
    
    def get_silence_duration(self) -> float:
        """Get how long it's been since AI finished speaking."""
        if not self.silence_check_start_time:
            return 0
        return time.time() - self.silence_check_start_time
    
    def has_user_spoken_since(self, check_start: float) -> bool:
        """Check if user has spoken since a specific time."""
        return self.last_user_speech_time and self.last_user_speech_time > check_start
    
    def check_silence(self, check_id: int) -> dict:
        """
        Check current silence status and return action needed.
        
        Args:
            check_id: ID of the silence check to validate
            
        Returns:
            dict with action: 'none', 'soft_prompt', 'hard_prompt', or 'abandon'
        """
        # Check if this check is still valid
        if not self.is_check_valid(check_id):
            logger.debug(f"⏹️ Silence check #{check_id} invalidated - AI spoke again")
            return {"action": "none", "reason": "check_invalidated"}
        
        if not self.silence_check_start_time:
            return {"action": "none"}
        
        # Check if user has spoken
        if self.has_user_spoken_since(self.silence_check_start_time):
            return {"action": "none", "reason": "user_spoke"}
        
        duration = self.get_silence_duration()
        
        # Abandon threshold (25s+)
        if duration >= ABANDON_THRESHOLD and self.silence_followup_count >= 2:
            logger.info(f"⏱️ Extended silence ({int(duration)}s) - abandon threshold reached")
            return {
                "action": "abandon",
                "duration": duration,
                "farewell": random.choice([
                    "I'll let you go. Feel free to call back anytime you need help with a booking!",
                    "No worries, I'll end the call here. Give us a ring when you're ready to book!",
                    "I'll wrap up here. Call us back anytime - we're here to help!"
                ])
            }
        
        # Hard threshold (20s)
        if duration >= HARD_SILENCE_THRESHOLD and self.silence_followup_count == 1:
            logger.info(f"⏱️ Hard silence ({int(duration)}s) - urgent check-in")
            self.silence_followup_count = 2
            return {
                "action": "hard_prompt",
                "duration": duration,
                "prompt": random.choice([
                    "Hello? I'm still here if you need anything.",
                    "Just checking - are you still on the line?",
                    "Hello? Let me know if there's anything else I can help with."
                ])
            }
        
        # Soft threshold (10s)
        if duration >= SOFT_SILENCE_THRESHOLD and self.silence_followup_count == 0:
            logger.info(f"⏱️ Soft silence ({int(duration)}s) - gentle check-in")
            self.silence_followup_count = 1
            return {
                "action": "soft_prompt",
                "duration": duration,
                "prompt": get_random_silence_prompt()
            }
        
        return {"action": "none"}
    
    def get_soft_threshold(self) -> float:
        """Get soft silence threshold with adjustment for thinking questions."""
        if self.ai_asked_question:
            return SOFT_SILENCE_THRESHOLD + 5  # Extra 5s for thinking
        return SOFT_SILENCE_THRESHOLD
    
    def get_hard_threshold(self) -> float:
        """Get hard silence threshold."""
        return HARD_SILENCE_THRESHOLD
    
    def get_abandon_threshold(self) -> float:
        """Get abandon threshold."""
        return ABANDON_THRESHOLD
