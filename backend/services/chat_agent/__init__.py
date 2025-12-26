"""
Chat Agent Package.

WhatsApp/Chat-based AI assistant for appointment booking businesses.
This module handles text-based conversations via Meta/WhatsApp API.

For voice-based AI, see: services.voice_agent

Usage:
    from services.chat_agent import generate_response
    
    response = await generate_response(
        history=[{"role": "user", "content": "I want to book..."}],
        customer_context="Returning customer",
        customer_id="customer_123",
        whatsapp_id="+61400123456"
    )
"""

from .orchestrator import generate_response
from .prompts import DEFAULT_SYSTEM_PROMPT, build_enhanced_prompt
from .tools import TOOLS
from .handlers import execute_tool
from .handlers import execute_tool
from services.meta import meta_service, MetaService

__all__ = [
    # Main entry point
    "generate_response",
    
    # Prompts
    "DEFAULT_SYSTEM_PROMPT",
    "build_enhanced_prompt",
    
    # Tools
    "TOOLS",
    "execute_tool",
    
    # Meta/WhatsApp service
    "meta_service",
    "MetaService",
]
