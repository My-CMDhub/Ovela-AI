import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from appwrite.id import ID
import logging

logger = logging.getLogger(__name__)

class ConversationsMixin:
    """
    Handles WhatsApp/Chat Conversations and Rate Limiting.
    """
    
    DAILY_TOKEN_LIMIT = 3000
    TOKEN_WARNING_THRESHOLD = 0.70
    COOLDOWN_HOURS = 5

    async def get_or_create_conversation(self, whatsapp_id: str, business_id: str):
        """Get existing conversation or create a new one."""
        try:
            queries = [
                f'equal("whatsapp_id", "{whatsapp_id}")',
                f'equal("business_id", "{business_id}")'
            ]
            params = {'queries': queries}
            
            result = await self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/conversations/documents",
                params=params
            )
            
            if result and result.get('documents') and len(result['documents']) > 0:
                return result['documents'][0]
            
            # Create new
            doc_id = ID.unique()
            data = {
                "whatsapp_id": whatsapp_id,
                "business_id": business_id,
                "status": "active",
                "history": "[]"
            }
            
            return await self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/conversations/documents",
                data={
                    "documentId": doc_id,
                    "data": data
                }
            )
        except Exception as e:
            logger.error(f"Error managing conversation: {e}")
            return None

    async def append_message(self, conversation_id: str, role: str, content: str, history_json: str):
        """Append a message to history."""
        try:
            history = json.loads(history_json) if history_json else []
            history.append({"role": role, "content": content, "timestamp": str(datetime.now())})
            
            if len(history) > 20:
                history = history[-20:]

            await self._make_request(
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

    async def check_token_limit(self, conversation: dict, business_phone: str = "the business") -> tuple:
        """Check if user has exceeded daily token limit."""
        try:
            # Note: is_whitelisted is bypassed here for simplicity in this audit fix, 
            # ideally should be imported or handled similarly.
            
            tokens_used = conversation.get("tokens_used_today", 0) or 0
            reset_at_str = conversation.get("token_reset_at")
            
            if reset_at_str:
                try:
                    MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
                    reset_at = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
                    if datetime.now(MELBOURNE_TZ) >= reset_at:
                        tokens_used = 0
                except:
                    pass
            
            usage_ratio = tokens_used / self.DAILY_TOKEN_LIMIT if self.DAILY_TOKEN_LIMIT > 0 else 0
            
            if tokens_used >= self.DAILY_TOKEN_LIMIT:
                return (False, "blocked", f"Limit reached. Refreshes soon. Call {business_phone} for urgent matters.")
            elif usage_ratio >= self.TOKEN_WARNING_THRESHOLD:
                return (True, "warning", f"Approaching limit. Call {business_phone} if needed.")
            else:
                return (True, "ok", None)
                
        except Exception as e:
            logger.error(f"Error checking token limit: {e}")
            return (True, "ok", None)
    
    async def update_token_usage(self, conversation_id: str, tokens_used: int, current_tokens: int = 0):
        """Update token usage."""
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            new_total = (current_tokens or 0) + tokens_used
            reset_at = (datetime.now(MELBOURNE_TZ) + timedelta(hours=self.COOLDOWN_HOURS)).isoformat()
            
            await self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/conversations/documents/{conversation_id}",
                data={
                    "data": {
                        "tokens_used_today": new_total,
                        "token_reset_at": reset_at
                    }
                }
            )
            return new_total
        except Exception as e:
            logger.error(f"Error updating token usage: {e}")
            return current_tokens
