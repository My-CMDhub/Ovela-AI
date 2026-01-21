"""
Voice Agent Configuration Module.

Contains all constants, thresholds, and configuration for the voice agent.
Easy to switch between demo and production environments.
"""

import random
from .audio_assets import BACKCHANNEL_AUDIO


# =============================================================================
# DEEPGRAM API
# =============================================================================
DEEPGRAM_AGENT_URL = "wss://agent.deepgram.com/v1/agent/converse"

# Greetings are now generated dynamically based on tenant
# See get_random_greeting(tenant_id) function below

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

FILLER_PROMPTS = [
    "Just a moment while I check that for you...",
    "Let me look that up real quick...",
    "Sure thing, checking on that now...",
    "Bear with me a sec, I'm checking the details...",
    "One moment please, let me verify that...",
    "Okay, let me see what I can find...",
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

# Soft warnings are now generated dynamically based on tenant
# See get_random_soft_warning(tenant_id) function below

MAX_VIOLATIONS_BEFORE_BAN = 3
REPETITIVE_INPUT_THRESHOLD = 3
MIN_SUBSTANTIVE_LENGTH = 3


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_random_greeting(tenant_id: str = "lydoun") -> str:
    """Returns a random Australian-tone greeting for the specified tenant."""
    # Saranda Restaurant
    if tenant_id == "saranda":
        greetings = [
            "Good day! You've reached Saranda Cafe and Pizzeria. How can I help you today?",
            "Hello! Thanks for calling Saranda. What can I get for you?",
            "Hi there! Saranda Cafe speaking. Are you after a pickup order or a reservation?",
            "Welcome to Saranda! How may I assist you today?",
            "Good to hear from you! This is Saranda Cafe. What can I do for you?",
            "Hello! Saranda Cafe and Pizzeria here. How can we help?",
        ]
        return random.choice(greetings)
    
    if tenant_id == "paddlesteamer":
        property_name = "Albury Paddlesteamer Motel"
        short_name = "Paddlesteamer Motel"
    else:
        property_name = "The Lydoun Motel"
        short_name = "Lydoun Motel"
    
    greetings = [
        f"G'day! {short_name}, Ovela speaking. How can I help you today?",
        f"Good day! {property_name}, this is Ovela. What can I do for you?",
        f"Hello there! You've reached {property_name}. I'm Ovela, how can I help?",
        f"Ovela is here, speaking from {short_name}. How can I assist you?",
        f"Hi there! This is Ovela at {property_name}. What can I help you with?",
    ]
    return random.choice(greetings)


def get_random_farewell() -> str:
    """Returns a random warm farewell."""
    return random.choice(FAREWELL_STYLES)


def get_random_silence_prompt() -> str:
    """Returns a random silence check-in prompt."""
    return random.choice(SILENCE_PROMPTS)


def get_random_soft_warning(tenant_id: str = "lydoun") -> str:
    """Returns a random soft warning for potential spam."""
    if tenant_id == "paddlesteamer":
        property_name = "Albury Paddlesteamer Motel"
        short_name = "Paddlesteamer"
    else:
        property_name = "The Lydoun Motel"
        short_name = "Lydoun"
    
    warnings = [
        f"I notice you might be having trouble. Is there something specific I can help with about {short_name}?",
        f"If you need a moment, no problem. I'm here to help with enquiries about {property_name}.",
        f"Just checking - were you after information about {property_name}?",
        f"I'm here to help with {short_name} enquiries. What dates were you thinking of staying?",
    ]
    return random.choice(warnings)



def get_random_filler_prompt() -> str:
    """Returns a random filler prompt to hold the floor."""
    return random.choice(FILLER_PROMPTS)


# =============================================================================
# SMART BACKCHANNEL AUDIO (Zero-Latency)
# =============================================================================
# Imported from audio_assets.py to keep config clean


def get_backchannel_audio(type: str = "neutral") -> str:
    """
    Get a random pre-cached backchannel audio chunk.
    Returns Base64 string or None if empty.
    """
    options = BACKCHANNEL_AUDIO.get(type, [])
    # Filter out empty placeholders
    valid = [opt for opt in options if opt]
    if not valid:
        return None
    return random.choice(valid)
