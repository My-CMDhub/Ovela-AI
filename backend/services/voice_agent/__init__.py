"""
Voice Agent Module.

A modular voice agent system that bridges Twilio Media Streams 
to Deepgram Voice Agent API with integrated abuse protection.

Usage:
    from services.voice_agent import VoiceAgentHandler
    
    handler = VoiceAgentHandler(websocket)
    await handler.start()

Structure:
    - config.py: All constants and configuration
    - prompts.py: System prompts and message templates
    - abuse_protection.py: Time-wasting/spam detection
    - silence_detection.py: Silence monitoring
    - functions/: Function calling handlers
    - bridges/: External API communication (Twilio, Deepgram)
"""

# Re-export main components for easy importing
from .config import (
    ABUSE_CONFIG,
    ENVIRONMENT,
    DEMO_CONFIG,
    PROD_CONFIG,
    get_random_greeting,
    get_random_farewell,
)

from .prompts import get_system_prompt

from .abuse_protection import AbuseProtection
from .silence_detection import SilenceMonitor

from .functions import get_booking_functions

from .bridges import TwilioBridge, DeepgramBridge

# Note: VoiceAgentHandler will be added once old file is refactored
# For now, continue using services.voice_deepgram_agent.DeepgramAgentHandler

__all__ = [
    # Config
    'ABUSE_CONFIG',
    'ENVIRONMENT', 
    'DEMO_CONFIG',
    'PROD_CONFIG',
    'get_random_greeting',
    'get_random_farewell',
    
    # Prompts
    'get_system_prompt',
    
    # Protection
    'AbuseProtection',
    'SilenceMonitor',
    
    # Functions
    'get_booking_functions',
    
    # Bridges
    'TwilioBridge',
    'DeepgramBridge',
]
