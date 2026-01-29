import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from appwrite.id import ID
from rules.whitelist import is_whitelisted
import logging

logger = logging.getLogger(__name__)

class ConversationsMixin:
    """
    Handles WhatsApp/Chat Conversations and Rate Limiting.
    """
    
    DAILY_TOKEN_LIMIT = 3000  # Max tokens per day per user
    TOKEN_WARNING_THRESHOLD = 0.70  # Warn at 70%
    COOLDOWN_HOURS = 5  # Hours until tokens reset

    def get_or_create_conversation(self, whatsapp_id: str, business_id: str):
        """Get existing conversation or create a new one."""
        try:
            queries = [
                f'equal("whatsapp_id", "{whatsapp_id}")',
                f'equal("business_id", "{business_id}")'
            ]
            params = {'queries': queries}
            
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/conversations/documents",
                params=params
            )
            
            if result and result.get('documents') and len(result['documents']) > 0:
                logger.info(f"Found existing conversation for {whatsapp_id}")
                return result['documents'][0]
            
            # Create new
            logger.info(f"Creating new conversation for {whatsapp_id}")
            doc_id = ID.unique()
            data = {
                "whatsapp_id": whatsapp_id,
                "business_id": business_id,
                "status": "active",
                "history": "[]"
            }
            
            new_doc = self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/conversations/documents",
                data={
                    "documentId": doc_id,
                    "data": data
                }
            )
            
            return new_doc
        except Exception as e:
            logger.error(f"Error managing conversation: {e}")
            return None

    def append_message(self, conversation_id: str, role: str, content: str, history_json: str):
        """Append a message to the conversation history."""
        try:
            history = json.loads(history_json) if history_json else []
            history.append({"role": role, "content": content, "timestamp": str(datetime.now())})
            
            # Keep only last 20 messages
            if len(history) > 20:
                history = history[-20:]

            self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/conversations/documents/{conversation_id}",
                data={
                    "data": {
                        "history": json.dumps(history),
                        "last_message": content
                    }
                }
            )
        except Exception as e:
            logger.error(f"Error appending message: {e}")

    def check_token_limit(self, conversation: dict, business_phone: str = "the business") -> tuple:
        """
        Check if user has exceeded daily token limit.
        Returns: (can_proceed: bool, status: str, message: str or None)
        status: 'ok', 'warning', 'blocked'
        """
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            
            # Check whitelist first
            if is_whitelisted(conversation.get("whatsapp_id")):
                logger.info(f" whitelist bypass for {conversation.get('whatsapp_id')}")
                return (True, "ok", None)

            tokens_used = conversation.get("tokens_used_today", 0) or 0
            reset_at_str = conversation.get("token_reset_at")
            
            # Check if we need to reset (5 hours passed)
            if reset_at_str:
                try:
                    reset_at = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
                    if datetime.now(MELBOURNE_TZ) >= reset_at:
                        # Reset tokens
                        tokens_used = 0
                except:
                    pass
            
            usage_ratio = tokens_used / self.DAILY_TOKEN_LIMIT if self.DAILY_TOKEN_LIMIT > 0 else 0
            
            if tokens_used >= self.DAILY_TOKEN_LIMIT:
                # Blocked - calculate when reset happens
                if reset_at_str:
                    try:
                        reset_at = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
                        reset_time = reset_at.strftime("%I:%M %p")
                    except:
                        reset_time = "a few hours"
                else:
                    reset_time = "a few hours"
                
                message = f"You've reached your chat limit for today. Your limit will refresh at {reset_time}. Please call {business_phone} for urgent matters. All your booking details are safely saved! 💜"
                return (False, "blocked", message)
            
            elif usage_ratio >= self.TOKEN_WARNING_THRESHOLD:
                # Warning - approaching limit
                remaining = self.DAILY_TOKEN_LIMIT - tokens_used
                message = f"Just a heads up — you're approaching your chat limit for today ({remaining} tokens remaining). If you need more help, feel free to call {business_phone} directly. Your limit will refresh in a few hours! 💜"
                return (True, "warning", message)
            
            else:
                # OK - proceed normally
                return (True, "ok", None)
                
        except Exception as e:
            logger.error(f"Error checking token limit: {e}")
            return (True, "ok", None)  # Fail open
    
    def update_token_usage(self, conversation_id: str, tokens_used: int, current_tokens: int = 0):
        """
        Update token usage for a conversation.
        Sets reset time if first usage of the day.
        """
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            new_total = (current_tokens or 0) + tokens_used
            
            # Set reset time if this is the start of a new period
            reset_at = (datetime.now(MELBOURNE_TZ) + timedelta(hours=self.COOLDOWN_HOURS)).isoformat()
            
            self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/conversations/documents/{conversation_id}",
                data={
                    "data": {
                        "tokens_used_today": new_total,
                        "token_reset_at": reset_at
                    }
                }
            )
            logger.info(f"Updated token usage: {new_total} tokens used")
            return new_total
        except Exception as e:
            logger.error(f"Error updating token usage: {e}")
            return current_tokens
