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

# Greetings are now generated dynamically based on tenant
# See get_random_greeting(tenant_id) function below

FAREWELL_STYLES = [
    "No worries, have a great one! Feel free to reach out when needed.",
    "Cheers, take care! Feel free to call whenever needed. Have a great day!",
    "All good, thanks for calling!",
    "Beauty, catch you later! Thanks for calling.",
    "Thanks for calling, have a lovely day! Bye.",
]

# Coal Creek Motel-specific farewells (motel hospitality style)
COALCREEK_FAREWELLS = [
    "Thanks for calling Coal Creek. Have a great stay.",
    "Perfect — we'll see you soon. Take care.",
    "All sorted. Safe travels.",
    "You're all set. Thanks for calling.",
    "Cheers — we'll have your room ready.",
]

SILENCE_PROMPTS = [
    "Still there?",
    "Hello?",
    "You there?",
    "Still with me?",
]

FILLER_PROMPTS = [
    "Just a moment while I check that for you...",
    "Let me look that up real quick...",
    "Sure thing, checking on that now...",
    "Bear with me a sec, I'm checking the details...",
    "One moment please, let me verify that...",
    "Okay, let me see what I can find...",
]

# Preset phrases to keep critical moments consistent and concise.
PRESET_PHRASES = {
    "coalcreek": {
        "availability_checking": "One moment, checking availability now.",
        "availability_fail": "Sorry, I can't access the live calendar right now. I'll transfer you to reception.",
        "transfering": "I'll put you through now.",
    },
    "default": {
        "availability_checking": "One moment, checking availability now.",
        "availability_fail": "Sorry, I can't check that right now. I'll transfer you to the team.",
        "transfering": "I'll put you through now.",
    },
}

# =============================================================================
# SILENCE DETECTION THRESHOLDS (seconds)
# =============================================================================
SOFT_SILENCE_THRESHOLD = 10   # First gentle check-in prompt
HARD_SILENCE_THRESHOLD = 15   # More urgent check
ABANDON_THRESHOLD = 25        # End call

# =============================================================================
# ABUSE PROTECTION CONFIG - Easy to switch between DEMO and PRODUCTION
# =============================================================================
from core.config import settings

# Active config based on environment
# Use global settings.ENVIRONMENT to respect the user's configuration
ENVIRONMENT = settings.ENVIRONMENT.lower()

# Demo settings (used for test/dev calls)
DEMO_CONFIG = {
    "context_pairs": 6,           # Conversation pairs to remember
    "soft_warning_minutes": 5,    # Gentle "wrapping up" prompt (5 min for demo)
    "hard_cap_minutes": 8,        # Maximum call duration (8 min for demo)
    "transfer_on_cap": False,     # Demo: Just hang up, don't transfer
    "off_topic_limit": 5,         # flag_off_topic calls before auto-hangup
    "human_escalation": False,    # No human escalation in demo
}

# Production settings (more lenient, with human escalation)
PROD_CONFIG = {
    "context_pairs": 8,           # More context for pattern detection
    "soft_warning_minutes": 10,    # More time for complex bookings
    "hard_cap_minutes": 12,       # Higher limit with escalation
    "transfer_on_cap": True,      # Production: Transfer to staff when cap reached
    "off_topic_limit": 3,         # Same threshold
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

# Soft warnings are now generated dynamically based on tenant
# See get_random_soft_warning(tenant_id) function below

MAX_VIOLATIONS_BEFORE_BAN = 3
REPETITIVE_INPUT_THRESHOLD = 3
MIN_SUBSTANTIVE_LENGTH = 3


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_random_greeting(tenant_id: str = "coalcreek") -> str:
    """Returns a random Australian-tone greeting for the specified tenant."""
    if tenant_id == "dhruv_personal":
        return "Hi, this is Nona, Dhruv's personal assistant. He's currently unavailable. May I ask who is calling?"

    # Coal Creek Motel
    if tenant_id == "coalcreek":
        greetings = [
            "Coal Creek Motel. This call is recorded. How can I help?",
            "Coal Creek Motel, this call is recorded. How can I help you today?",
            "Coal Creek Motel. Calls are recorded. What can I do for you?",
            "Coal Creek Motel here. This call is recorded. How can I help?",
            "Coal Creek Motel. Calls are recorded. Are you after a room or info?",
            "Coal Creek Motel — calls are recorded. What can I help with?",
            "Coal Creek Motel. This call's recorded. How can I help?",
        ]
        return random.choice(greetings)
    
    # Default fallback for unknown tenants
    return "Hello! This is Ovela. How can I help you today?"


def get_random_farewell(tenant_id: str = None) -> str:
    """Returns a random warm farewell for the specified tenant."""
    if tenant_id == "dhruv_personal":
        return "I have sent a message to Dhruv, he will call you back as soon as he can. Goodbye."
    if tenant_id == "coalcreek":
        return random.choice(COALCREEK_FAREWELLS)
    # Add other tenants here as needed (saranda, etc.)
    return random.choice(FAREWELL_STYLES)


def get_random_silence_prompt() -> str:
    """Returns a random silence check-in prompt."""
    return random.choice(SILENCE_PROMPTS)


def get_random_soft_warning(tenant_id: str = "coalcreek") -> str:
    """Returns a random soft warning for potential spam."""
    # Coal Creek Motel
    if tenant_id == "coalcreek":
        warnings = [
            "I notice you might be having trouble. Is there something specific I can help with about Coal Creek Motel?",
            "If you need a moment, no problem. I'm here to help with enquiries about Coal Creek Motel.",
            "Just checking - were you after information about Coal Creek Motel or making a booking?",
            "I'm here to help with Coal Creek Motel enquiries. What dates were you thinking of staying?",
        ]
        return random.choice(warnings)
    
    # Default fallback
    return "I notice you might be having trouble. Is there something specific I can help with?"



def get_random_filler_prompt() -> str:
    """Returns a random filler prompt to hold the floor."""
    return random.choice(FILLER_PROMPTS)


def get_preset_phrase(tenant_id: str, key: str) -> str:
    """Return a preset phrase for consistent critical messaging."""
    tenant_map = PRESET_PHRASES.get(tenant_id, PRESET_PHRASES["default"])
    return tenant_map.get(key, PRESET_PHRASES["default"].get(key, ""))

