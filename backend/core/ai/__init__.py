# AI Module Package
# Modular architecture for scalability and maintainability

from .prompts import DEFAULT_SYSTEM_PROMPT, build_enhanced_prompt
from .tools import TOOLS
from .handlers import execute_tool
from .orchestrator import generate_response

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "build_enhanced_prompt", 
    "TOOLS",
    "execute_tool",
    "generate_response"
]
