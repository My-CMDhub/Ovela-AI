"""
AI Module - Backwards Compatibility Layer
=========================================
This file maintains backwards compatibility for existing imports.
The module has been refactored into a modular structure under core/ai/

New Structure:
- core/ai/prompts.py     - System prompt and prompt builder
- core/ai/tools.py       - Tool definitions for OpenAI function calling
- core/ai/handlers.py    - Tool execution handlers
- core/ai/orchestrator.py - Main generate_response function

To use the new structure directly:
    from core.ai import generate_response, TOOLS, execute_tool

Legacy imports (this file) still work:
    from core.ai import generate_response
"""

# Re-export everything from the new modular structure
from core.ai import (
    DEFAULT_SYSTEM_PROMPT,
    build_enhanced_prompt,
    TOOLS,
    execute_tool,
    generate_response
)

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "build_enhanced_prompt",
    "TOOLS", 
    "execute_tool",
    "generate_response"
]
