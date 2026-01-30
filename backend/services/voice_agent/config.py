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
    "Thanks for calling Coal Creek Motel! Have a great stay. Bye!",
    "Perfect! We look forward to seeing you. Take care!",
    "All sorted! Safe travels, and see you soon. Bye!",
    "You're all set! Thanks for choosing Coal Creek. Bye!",
    "Cheers! We'll have your room ready. Goodbye!",
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
from core.config import settings

# Active config based on environment
# Use global settings.ENVIRONMENT to respect the user's configuration
ENVIRONMENT = settings.ENVIRONMENT.lower()

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
    "soft_warning_minutes": 1,    # More time for complex bookings
    "hard_cap_minutes": 1.2,       # Higher limit with escalation
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
    # Saranda Restaurant
    if tenant_id == "saranda":
        greetings = [
            "Good day! You've reached Saranda Cafe and Pizzeria. Calls are recorded for quality assurance. How can I help you today?",
            "Hello! Thanks for calling Saranda. Just letting you know this call is recorded for quality purposes. What can I get for you?",
            "Hi there! Saranda Cafe speaking. Please note calls are recorded for quality and training purposes. Are you after a pickup order or a reservation?",
            "Welcome to Saranda! This call is recorded for quality training purposes. How may I assist you today?",
            "Good to hear from you! This is Saranda Cafe. Calls are recorded. What can I do for you?",
        ]
        return random.choice(greetings)
    
    # Coal Creek Motel
    if tenant_id == "coalcreek":
        greetings = [
            "G'day! Coal Creek Motel, Ovela speaking. Please note this call is recorded for quality and training purposes. How can I help you today?",
            "Hello! Thanks for calling Coal Creek Motel. Just letting you know this call is recorded for quality and training purposes. What can I do for you?",
            "Hi there! Coal Creek Motel speaking. Please note calls are recorded for quality and training purposes. Are you after a room or some information?",
            "Good day! You've reached Coal Creek Motel in Korumburra. Calls are recorded for quality and training purposes. How can I help?",
            "Welcome to Coal Creek Motel! This is Ovela. Please note this call is recorded for quality and training purposes. What can I assist you with?",
        ]
        return random.choice(greetings)
    
    # Default fallback for unknown tenants
    return "Hello! This is Ovela. How can I help you today?"


def get_random_farewell(tenant_id: str = None) -> str:
    """Returns a random warm farewell for the specified tenant."""
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
    
    # Saranda Restaurant
    if tenant_id == "saranda":
        warnings = [
            "I notice you might be having trouble. Is there something specific I can help with about Saranda Cafe?",
            "If you need a moment, no problem. I'm here to help with orders and reservations.",
            "Just checking - were you after a pickup order or a table reservation?",
            "I'm here to help with Saranda enquiries. What can I get for you?",
        ]
        return random.choice(warnings)
    
    # Default fallback
    return "I notice you might be having trouble. Is there something specific I can help with?"



def get_random_filler_prompt() -> str:
    """Returns a random filler prompt to hold the floor."""
    return random.choice(FILLER_PROMPTS)

