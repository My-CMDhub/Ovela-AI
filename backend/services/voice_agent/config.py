"""
Voice Agent Configuration Module.

Contains all constants, thresholds, and configuration for the voice agent.
Easy to switch between demo and production environments.
"""

import random

# =============================================================================
# DEEPGRAM API
# =============================================================================
DEEPGRAM_AGENT_URL = "wss://agent.deepgram.com/v1/agent/converse"

# =============================================================================
# GREETINGS & FAREWELLS - Australian-tone for natural variety
# =============================================================================
GREETINGS_POOL = [
    "G'day! Lydoun Motel, Ovela speaking. How can I help you today?",
    "Good day! The Lydoun Motel, this is Ovela. What can I do for you?",
    "Hello there! You've reached The Lydoun Motel. I'm Ovela, how can I help?",
    "Ovela is here, speaking from Lydoun Motel. How can I assist you?",
    "Hi there! This is Ovela at The Lydoun Motel. What can I help you with?",
]

FAREWELL_STYLES = [
    "No worries, have a great one! feel free to reach out us when needed",
    "Cheers, take care! feel free to call use whenever needed. Have a greate day",
    "All good, thanks for calling!",
    "Beauty, catch you later! Thanks for calling",
    "Thanks for calling, have a lovely day! Bye",
]

SILENCE_PROMPTS = [
    "Hello? Still there?",
    "Can you hear me alright?",
    "Take your time, I'm here when you're ready.",
    "No rush, just checking you're still on the line.",
    "Hello? Are you still with me?",
]

# =============================================================================
# SILENCE DETECTION THRESHOLDS (seconds)
# =============================================================================
SOFT_SILENCE_THRESHOLD = 10   # First gentle check-in prompt
HARD_SILENCE_THRESHOLD = 20   # More urgent check
ABANDON_THRESHOLD = 25        # End call

# =============================================================================
# ABUSE PROTECTION CONFIG - Easy to switch between DEMO and PRODUCTION
# =============================================================================
ENVIRONMENT = "demo"  # Change to "production" for prod settings

# Demo settings (stricter for testing - public demos)
DEMO_CONFIG = {
    "context_pairs": 6,           # Conversation pairs to remember
    "soft_warning_minutes": 2,    # Gentle "wrapping up" prompt (2 min for demo)
    "hard_cap_minutes": 3,        # Maximum call duration (3 min for demo)
    "transfer_on_cap": False,     # Demo: Just hang up, don't transfer
    "off_topic_limit": 5,         # flag_off_topic calls before auto-hangup
    "human_escalation": False,    # No human escalation in demo
}

# Production settings (more lenient, with human escalation)
PROD_CONFIG = {
    "context_pairs": 8,           # More context for pattern detection
    "soft_warning_minutes": 8,    # More time for complex bookings
    "hard_cap_minutes": 12,       # Higher limit with escalation
    "transfer_on_cap": True,      # Production: Transfer to staff when cap reached
    "off_topic_limit": 5,         # Same threshold
    "human_escalation": True,     # Log for human follow-up
}

# Active config based on environment
ABUSE_CONFIG = DEMO_CONFIG if ENVIRONMENT == "demo" else PROD_CONFIG

# =============================================================================
# THINKING PATTERNS - User might need extra time to respond
# =============================================================================
THINKING_PATTERNS = [
    "what dates", "when would", "how many", "which room",
    "would you like", "do you need", "can you tell me",
    "let me know", "think about", "decide",
]

# =============================================================================
# SPAM DETECTION
# =============================================================================
SPAM_PATTERNS = [
    r'^[a-z]{1,2}$',  # Single or double character responses
    r'^(ha|he|ho|la|na|ya)+$',  # Repeated syllables
    r'^[\W\d]+$',  # Only numbers/symbols
]

SOFT_WARNINGS = [
    "I notice you might be having trouble. Is there something specific I can help with about the motel?",
    "If you need a moment, no problem. I'm here to help with room enquiries and bookings.",
    "Just checking - were you after information about The Lydoun Motel?",
    "I'm here to help with motel enquiries. What dates were you thinking of staying?",
]

MAX_VIOLATIONS_BEFORE_BAN = 3
REPETITIVE_INPUT_THRESHOLD = 3
MIN_SUBSTANTIVE_LENGTH = 3


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_random_greeting() -> str:
    """Returns a random Australian-tone greeting."""
    return random.choice(GREETINGS_POOL)


def get_random_farewell() -> str:
    """Returns a random warm farewell."""
    return random.choice(FAREWELL_STYLES)


def get_random_silence_prompt() -> str:
    """Returns a random silence check-in prompt."""
    return random.choice(SILENCE_PROMPTS)


def get_random_soft_warning() -> str:
    """Returns a random soft warning for potential spam."""
    return random.choice(SOFT_WARNINGS)
