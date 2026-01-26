"""
Voice Agent Prompts Module.

Contains system prompts, message templates, and conversation guidance.
"""

from services.voice_agent.prompts_saranda import get_saranda_prompt
from services.voice_agent.prompts_coalcreek import get_coalcreek_prompt

def get_system_prompt(current_date: str = None, current_time: str = None, tenant_id: str = "coalcreek") -> str:
    """
    Returns the full system prompt for the AI agent.
    
    This prompt defines the agent's personality, knowledge, and behavior.
    Uses dedicated prompts for each tenant.
    
    Args:
        current_date: Current date string
        current_time: Current time string
        tenant_id: Tenant identifier (saranda, coalcreek)
    """
    # Saranda Restaurant (pickup orders, WhatsApp HITL)
    if tenant_id == "saranda":
        return get_saranda_prompt(current_date, current_time)
    
    # Coal Creek Motel (Default/Primary)
    # Also handles fallback if tenant_id is unknown or legacy
    return get_coalcreek_prompt(current_date, current_time)
