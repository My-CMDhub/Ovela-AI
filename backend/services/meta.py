import httpx
from core.config import settings
import logging

logger = logging.getLogger(__name__)

class MetaService:
    def __init__(self):
        self.api_url = f"https://graph.facebook.com/v18.0/{settings.META_PHONE_NUMBER_ID}/messages"
        self.headers = {
            "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

    async def send_text_message(self, to_phone_number: str, text: str):
        """
        Sends a text message to a WhatsApp user.
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone_number,
            "text": {"body": text}
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.api_url, headers=self.headers, json=payload)
                response.raise_for_status()
                logger.info(f"Message sent to {to_phone_number}: {response.json()}")
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send message: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None

meta_service = MetaService()
