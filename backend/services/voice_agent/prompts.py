"""
Voice Agent Prompts Module.

Contains system prompts, message templates, and conversation guidance.
"""

from services.voice_agent.prompts_coalcreek import get_coalcreek_prompt

def get_system_prompt(current_date: str = None, current_time: str = None, tenant_id: str = "coalcreek") -> str:
    """
    Returns the full system prompt for the AI agent.
    
    This prompt defines the agent's personality, knowledge, and behavior.
    Uses dedicated prompts for each tenant.
    
    Args:
        current_date: Current date string
        current_time: Current time string
        tenant_id: Tenant identifier (currently only coalcreek is active)
    """
    # Coal Creek Motel (Primary tenant)
    # Multi-tenant architecture preserved for future expansion
    return get_coalcreek_prompt(current_date, current_time)

