"""
Voice Agent Abuse Protection Module.

Handles detection and escalation of time-wasting, off-topic behavior,
and enforces time caps on calls.
"""

import asyncio
import logging
import time
import re

from .config import (
    ABUSE_CONFIG,
    SPAM_PATTERNS,
    MAX_VIOLATIONS_BEFORE_BAN,
    REPETITIVE_INPUT_THRESHOLD,
    MIN_SUBSTANTIVE_LENGTH,
    get_random_soft_warning,
)

logger = logging.getLogger(__name__)


class AbuseProtection:
    """
    Tracks off-topic behavior, spam patterns, and enforces time caps.
    
    Thresholds (from ABUSE_CONFIG):
    - 1-2 flags: Gentle redirect
    - 3-(limit-1) flags: Firm redirect
    - limit+ flags: Auto-hangup with polite message
    """
    
    def __init__(self, tenant_id: str = "coalcreek"):
        # Off-topic tracking
        self.off_topic_count = 0
        
        # Time cap tracking
        self.time_warning_sent = False
        self.call_start_time = None
        
        # Spam tracking
        self.violation_count = 0
        self.warnings_sent = 0
        self.last_inputs = []  # Track last 5 inputs for pattern detection
        self.short_response_count = 0
        
        # Tenant-specific details
        self.tenant_id = tenant_id
        
        if tenant_id == "saranda":
            self.property_name = "Saranda Restaurant"
            self.short_name = "Saranda"
        elif tenant_id == "coalcreek":
            self.property_name = "Coal Creek Motel"
            self.short_name = "Coal Creek"
        else:
            # Generic Fallback for unknown tenants
            self.property_name = "Our Business"
            self.short_name = "Staff"
    
    def set_call_start_time(self, start_time: float):
        """Set when the call started for duration monitoring."""
        self.call_start_time = start_time
    
    def flag_off_topic(self, reason: str) -> dict:
        """
        Increment off-topic counter and return escalation response.
        
        Args:
            reason: Why this is off-topic (e.g., 'flirting', 'personal', 'why chain')
            
        Returns:
            dict with count, stage, action, and message for AI to follow
        """
        limit = ABUSE_CONFIG["off_topic_limit"]
        
        self.off_topic_count += 1
        count = self.off_topic_count
        
        logger.info(f"⚠️ Off-topic flag #{count}/{limit}: {reason}")
        
        # Stage 1: Gentle redirect (1-2 flags)
        if count <= 2:
            return {
                "count": count,
                "limit": limit,
                "stage": 1,
                "action": "redirect_gently",
                "message": "This seems off-topic. Briefly acknowledge, then ask: 'Is there anything about the motel or booking I can help you with?'"
            }
        
        # Stage 2: Firm redirect (3 to limit-1 flags)
        elif count < limit:
            return {
                "count": count,
                "limit": limit,
                "stage": 2,
                "action": "redirect_firmly",
                "message": f"This is off-topic comment #{count}. Say: 'I'm really here to help with motel or booking. If there's nothing else I can help with, we should wrap up our call.'"
            }
        
        # Stage 3: Auto-hangup (limit+ flags)
        else:
            logger.info(f"🚫 Off-topic limit reached ({count}/{limit} flags) - requesting hangup")
            return {
                "count": count,
                "limit": limit,
                "stage": 3,
                "action": "hangup",
                "should_hangup": True,
                "farewell": "I've really enjoyed chatting, but I need to free up the line for other callers. If you ever need help with motel or booking, give us a call back anytime. Take care!",
                "message": "LIMIT REACHED. The system is ending the call. Say your farewell - the call will end shortly."
            }
    
    def check_duration(self) -> dict:
        """
        Check if call duration has exceeded thresholds.
        
        Returns:
            dict with action needed:
            - None: No action needed
            - 'soft_warning': Send soft warning message
            - 'hard_cap': End call
        """
        if not self.call_start_time:
            return {"action": None}
        
        soft_seconds = ABUSE_CONFIG["soft_warning_minutes"] * 60
        hard_seconds = ABUSE_CONFIG["hard_cap_minutes"] * 60
        
        elapsed = time.time() - self.call_start_time
        
        # Hard cap check first
        if elapsed >= hard_seconds:
            minutes = int(elapsed / 60)
            logger.info(f"🚫 Hard time cap reached at {minutes} minutes")
            
            if ABUSE_CONFIG.get("human_escalation"):
                farewell = (
                    "I've really enjoyed helping you, but due to our call time guidelines, "
                    "I need to wrap up now. Don't worry - I'm logging this conversation and "
                    "a member of our team will reach out to help with anything we didn't finish. "
                    f"They'll pick up right where we left off. Thanks so much for calling {self.short_name}!"
                )
            else:
                farewell = (
                    "I've really enjoyed helping you today, but I need to free up the line "
                    "for other callers. If you need anything else, feel free to call back anytime. "
                    "Take care and have a great day!"
                )
            
            return {
                "action": "hard_cap",
                "should_hangup": True,
                "farewell": farewell,
                "outcome": "timeout_duration"
            }
        
        # Soft warning check
        if elapsed >= soft_seconds and not self.time_warning_sent:
            self.time_warning_sent = True
            minutes = int(elapsed / 60)
            logger.info(f"⏱️ Soft time warning at {minutes} minutes")
            
            return {
                "action": "soft_warning",
                "message": (
                    "Just to let you know, we've been chatting for a while. "
                    "Is there anything else about motel or booking I can help wrap up quickly?"
                )
            }
        
        return {"action": None}
    
    def check_spam_behavior(self, user_input: str) -> dict:
        """
        Analyze user input for spam/abuse patterns.
        
        Args:
            user_input: The user's transcribed speech
            
        Returns:
            dict with 'is_spam' bool and optional 'warning' message
        """
        user_input = user_input.strip().lower()
        
        # Check against spam patterns
        for pattern in SPAM_PATTERNS:
            if re.match(pattern, user_input):
                self.violation_count += 1
                logger.warning(f"🚨 Spam pattern detected: '{user_input}' (violations: {self.violation_count})")
                
                if self.violation_count >= MAX_VIOLATIONS_BEFORE_BAN:
                    return {
                        "is_spam": True,
                        "should_hangup": True,
                        "message": "I'm having trouble understanding. Let's end here - call back when you're ready to chat about a booking."
                    }
                else:
                    return {
                        "is_spam": True,
                        "warning": get_random_soft_warning(self.tenant_id)
                    }
        
        # Track repetitive inputs
        self.last_inputs.append(user_input)
        if len(self.last_inputs) > 5:
            self.last_inputs.pop(0)
        
        # Check for repetitive behavior
        if len(self.last_inputs) >= REPETITIVE_INPUT_THRESHOLD:
            last_n = self.last_inputs[-REPETITIVE_INPUT_THRESHOLD:]
            if len(set(last_n)) == 1:  # All same
                self.violation_count += 1
                logger.warning(f"🔄 Repetitive input detected (violations: {self.violation_count})")
                return {
                    "is_spam": True,
                    "warning": "I noticed you've said that a few times. Is there something specific about motel or booking I can help with?"
                }
        
        # Track short/non-substantive responses
        if len(user_input) < MIN_SUBSTANTIVE_LENGTH:
            self.short_response_count += 1
            if self.short_response_count >= 5:
                return {
                    "is_spam": False,
                    "warning": get_random_soft_warning(self.tenant_id)
                }
        else:
            self.short_response_count = 0
        
        return {"is_spam": False}
