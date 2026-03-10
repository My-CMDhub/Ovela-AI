"""
Voice Agent Prompts Module.

Contains system prompts, message templates, and conversation guidance.
"""

from services.voice_agent.prompts_coalcreek import get_coalcreek_prompt
from services.voice_agent.prompts_dhruv import get_dhruv_personal_prompt

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
    # Personal Assistant Route
    if tenant_id == "dhruv_personal":
        return get_dhruv_personal_prompt(current_date, current_time)

    # Coal Creek Motel (Primary tenant)
    # Multi-tenant architecture preserved for future expansion
    return get_coalcreek_prompt(current_date, current_time)

