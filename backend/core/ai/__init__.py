"""
DEPRECATED: AI Module has moved to services.chat_agent

This package re-exports from the new location for backwards compatibility.

Please update your imports:
    # Old (deprecated)
    from core.ai import generate_response
    
    # New (recommended)
    from services.chat_agent import generate_response
"""

import warnings

# Re-export from new location
from services.chat_agent import (
    generate_response,
    DEFAULT_SYSTEM_PROMPT,
    build_enhanced_prompt,
    TOOLS,
    execute_tool,
)

# Show deprecation warning on import
warnings.warn(
    "core.ai is deprecated. Import from services.chat_agent instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "build_enhanced_prompt", 
    "TOOLS",
    "execute_tool",
    "generate_response"
]
