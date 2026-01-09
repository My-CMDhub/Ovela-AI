"""
AI Tool Definitions
OpenAI function calling tool schemas for the booking system.
"""

"""
AI Tool Definitions
OpenAI function calling tool schemas for the booking system.
"""

from services.voice_agent.functions import get_booking_functions

# Use the same tools as the voice agent for consistency
TOOLS = get_booking_functions()

