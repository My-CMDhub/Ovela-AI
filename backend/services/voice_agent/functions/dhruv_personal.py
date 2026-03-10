"""
Personal Assistant Function Definitions and Handlers.
"""
import os
import logging
from services.sms import sms_service
from core.config import settings

logger = logging.getLogger(__name__)

def get_personal_assistant_functions() -> list:
    """Returns the function definition for the personal assistant use case."""
    return [
        {
            "name": "send_message_to_dhruv",
            "description": "Send a text message to Dhruv summarizing the caller's query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {
                        "type": "string",
                        "description": "The name of the caller"
                    },
                    "reason": {
                        "type": "string",
                        "description": "A very concise summary of why they are calling"
                    }
                },
                "required": ["caller_name", "reason"]
            }
        }
    ]

async def handle_send_message_to_dhruv(args: dict, user_phone: str) -> dict:
    """Handles the execution of sending the message via SMS.
    Note: We actually don't send the SMS mid-call anymore. The VoiceAgentHandler
    summarizes the entire call transcript and sends it upon disconnection if duration > 6s.
    This function just acts as a conversational placemarker so the AI knows it succeeded.
    """
    caller_name = args.get("caller_name", "Unknown caller")
    reason = args.get("reason", "No reason provided")
    
    logger.info(f"📝 Noted message from {caller_name}: {reason} (Will be sent at call-end)")
    return {"success": True, "message": "Message successfully noted and will be passed to Dhruv when the call ends."}
