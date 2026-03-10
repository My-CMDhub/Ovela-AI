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
    """Handles the execution of sending the message via SMS."""
    caller_name = args.get("caller_name", "Unknown caller")
    reason = args.get("reason", "No reason provided")
    
    # Text to send to Dhruv
    message = f"New Call from {caller_name} ({user_phone}):\nReason: {reason}"
    
    # Send to MY_NUMBER
    my_number = os.getenv("MY_NUMBER") or settings.MY_NUMBER
    if not my_number:
        logger.error("MY_NUMBER not set! Cannot send SMS to personal number.")
        return {"success": False, "message": "The assistant system is not configured correctly to send messages."}
        
    success = await sms_service.send_sms(to_number=my_number, message=message, tenant_id="dhruv_personal")
    
    if success:
        return {"success": True, "message": "Message successfully passed on to Dhruv."}
    else:
        return {"success": False, "message": "Failed to pass the message."}
