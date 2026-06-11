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
    get_random_silence_farewell,
)

logger = logging.getLogger(__name__)


class SilenceMonitor:
    """
    Monitors for extended silence and triggers prompts or call end.
    
    Thresholds:
    - SOFT_SILENCE_THRESHOLD (10s): First gentle check-in
    - HARD_SILENCE_THRESHOLD (15s): More urgent check
    - ABANDON_THRESHOLD (25s): End call politely
    """
    
    def __init__(self):
        self.last_user_speech_time = None
        self.silence_followup_sent = False
        self.silence_followup_count = 0
        self.silence_check_start_time = None
        self.silence_check_id = 0  # Counter to invalidate old checks
        self.silence_pause_end_time = None
        self.last_ai_message = ""
        self.ai_asked_question = False

    def on_user_speech(self):
        """Called when user starts speaking - resets silence tracking."""
        self.last_user_speech_time = time.time()
        self.silence_followup_sent = False
        self.silence_followup_count = 0
        self.silence_pause_end_time = None  # User speaking cancels any active wait/pause
        self.silence_check_id += 1  # Immediately invalidate any mid-sleep silence check
        
    def on_ai_started_speaking(self, preserve_check_id: bool = False):
        """
        Called when AI starts speaking - invalidate pending silence checks.
        
        Args:
            preserve_check_id: If True, preserve state for escalation sequence
                               (don't increment check ID or reset timing)
        """
        if not preserve_check_id:
            self.silence_check_id += 1  # Invalidate any running checks
            self.silence_check_start_time = None  # Reset timing
        # During escalation: keep check_id and start_time intact
    
    def on_ai_finished_speaking(self, message: str = "", preserve_escalation: bool = False):
        """
        Called when AI finishes speaking (AgentAudioDone) - starts silence timer.

        Args:
            preserve_escalation: When True (system audio played during escalation),
                preserve the original silence timer, check id, and followup count
                so the hard→abandon chain stays valid against the same silence window.
                Only reset them when a genuine new AI turn begins.
        """
        # Start a new silence window only for a genuine new AI turn.
        # During silence escalation prompts, keep counting from the original
        # post-AI silence start, otherwise the 15s/25s stages never arrive.
        if not preserve_escalation:
            self.silence_check_start_time = time.time()
            self.silence_check_id += 1
            self.last_ai_message = message
            self.ai_asked_question = self._requires_thinking(message) if message else False
            self.silence_followup_count = 0
            self.silence_followup_sent = False
        self.tts_buffer = 0  # No buffer - rely on state machine
    
    def _requires_thinking(self, message: str) -> bool:
        """Check if the AI's message requires user to think (longer threshold)."""
        message_lower = message.lower()
        return any(pattern in message_lower for pattern in THINKING_PATTERNS)
    
    def get_tts_buffer(self) -> float:
        """Get the TTS playback buffer time (added to sleep time in handler)."""
        return getattr(self, 'tts_buffer', 0)
    
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
        
    def pause_silence(self, seconds: float):
        """
        Pause silence detection for a specific duration.
        """
        self.silence_pause_end_time = time.time() + seconds
    
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
            
        # Check if we are currently in an active pause
        if self.silence_pause_end_time and time.time() < self.silence_pause_end_time:
            # We are inside the explicit wait duration requested by the user.
            # However, if duration keeps extending, we should still update check start time 
            # so when the pause ends, it starts counting from 0 again.
            self.silence_check_start_time = time.time()
            return {"action": "none", "reason": "paused_on_request"}
        else:
            # Pause expired or cleared
            self.silence_pause_end_time = None
        
        # Check if user has spoken
        if self.has_user_spoken_since(self.silence_check_start_time):
            return {"action": "none", "reason": "user_spoke"}
        
        duration = self.get_silence_duration()
        hard_threshold = self.get_hard_threshold()
        
        # Abandon threshold (25s+)
        if duration >= ABANDON_THRESHOLD and self.silence_followup_count >= 2:
            logger.info(f"⏱️ Extended silence ({int(duration)}s) - abandon threshold reached")
            return {
                "action": "abandon",
                "duration": duration,
                "farewell": get_random_silence_farewell(),
            }
        
        # Hard threshold (15s by default, or 5s after any extended soft threshold)
        if duration >= hard_threshold and self.silence_followup_count == 1:
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
        return max(HARD_SILENCE_THRESHOLD, self.get_soft_threshold() + 5)
    
    def get_abandon_threshold(self) -> float:
        """Get abandon threshold."""
        return ABANDON_THRESHOLD

    def stop(self):
        """Stop silence monitoring permanently for this call."""
        self.silence_check_start_time = None
        self.silence_check_id += 1  # Invalidate any running checks
        self.silence_pause_end_time = float('inf')  # Pause forever

