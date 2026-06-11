"""
Voice Agent Module.

A modular voice agent system that bridges Twilio Media Streams 
to Deepgram Voice Agent API with integrated abuse protection.

Usage:
    from services.voice_agent import VoiceAgentHandler
    
    handler = VoiceAgentHandler(websocket)
    await handler.start()

Structure:
    - handler.py: Main VoiceAgentHandler class
    - config.py: All constants and configuration
    - prompts.py: System prompts and message templates
    - abuse_protection.py: Time-wasting/spam detection
    - silence_detection.py: Silence monitoring
    - functions/: Function definitions and handlers
    - bridges/: External API communication (Twilio, Deepgram)
"""

# Re-export main components for easy importing
from .config import (
    ABUSE_CONFIG,
    ENVIRONMENT,
    DEMO_CONFIG,
    PROD_CONFIG,
    DEEPGRAM_AGENT_URL,
    get_random_greeting,
    get_random_farewell,
)

from .prompts import get_system_prompt

from .abuse_protection import AbuseProtection
from .silence_detection import SilenceMonitor

from .functions import get_booking_functions

# Main handler - optional import (requires twilio, websockets)
try:
    from .handler import VoiceAgentHandler, DeepgramAgentHandler
    _handler_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).error(f"Failed to import VoiceAgentHandler: {e}")
    VoiceAgentHandler = None
    DeepgramAgentHandler = None
    _handler_available = False

# Optional bridges import - may fail if twilio is not installed
try:
    from .bridges import TwilioBridge, DeepgramBridge
    _bridges_available = True
except ImportError:
    TwilioBridge = None
    DeepgramBridge = None
    _bridges_available = False

__all__ = [
    # Main Handler
    'VoiceAgentHandler',
    'DeepgramAgentHandler',  # Backwards compatibility alias
    
    # Config
    'ABUSE_CONFIG',
    'ENVIRONMENT', 
    'DEMO_CONFIG',
    'PROD_CONFIG',
    'DEEPGRAM_AGENT_URL',
    'get_random_greeting',
    'get_random_farewell',
    
    # Prompts
    'get_system_prompt',
    
    # Protection
    'AbuseProtection',
    'SilenceMonitor',
    
    # Functions
    'get_booking_functions',
]

# Add bridges to __all__ only if available
if _bridges_available:
    __all__.extend(['TwilioBridge', 'DeepgramBridge'])

