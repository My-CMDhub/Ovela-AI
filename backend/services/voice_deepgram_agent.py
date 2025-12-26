"""
DEPRECATED: This module is deprecated.

The voice agent has been refactored into a modular package at:
    services/voice_agent/

Please update your imports:
    # Old (deprecated)
    from services.voice_deepgram_agent import DeepgramAgentHandler
    
    # New (recommended)
    from services.voice_agent import VoiceAgentHandler

The DeepgramAgentHandler name is kept for backwards compatibility.
"""

import warnings

# Re-export from new location for backwards compatibility
from services.voice_agent import VoiceAgentHandler

# Backwards compatibility alias with deprecation warning
class DeepgramAgentHandler(VoiceAgentHandler):
    """
    DEPRECATED: Use VoiceAgentHandler from services.voice_agent instead.
    
    This class is kept for backwards compatibility only.
    """
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "DeepgramAgentHandler is deprecated. Use VoiceAgentHandler from "
            "services.voice_agent instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)

# Also re-export common items for any code that imports them from here
from services.voice_agent import (
    ABUSE_CONFIG,
    get_system_prompt,
    get_booking_functions,
    AbuseProtection,
    SilenceMonitor,
)
