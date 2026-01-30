import logging
import httpx
from core.config import settings
from core.utils import mask_phone

logger = logging.getLogger(__name__)

class SmsService:
    def __init__(self):
        self.client = None
        self.from_number = settings.TWILIO_PHONE_NUMBER
        
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            logger.warning("Twilio credentials missing - SMS service disabled")

    async def send_sms(self, to_number: str, message: str, tenant_id: str = None) -> bool:
        """
        Send an SMS message via async httpx.
        
        Args:
            to_number: Recipient phone number
            message: Message body
            tenant_id: Optional tenant ID to resolve 'From' number dynamically
        """
        if not settings.TWILIO_ACCOUNT_SID:
            logger.warning("SMS service not configured - skipping SMS")
            return False
            
        try:
            # Determine sender number
            from_number = self.from_number
            
            if tenant_id:
                try:
                    from services.appwrite import db_service
                    tenant_config = await db_service.get_tenant_config(tenant_id)
                    if tenant_config and tenant_config.get("twilio_phone"):
                        from_number = tenant_config["twilio_phone"]
                        logger.debug(f"Using dynamic sender for {tenant_id}: {from_number}")
                except Exception as e:
                    logger.warning(f"Failed to resolve tenant specific sender: {e}")
            
            clean_number = to_number.strip().replace(" ", "")
            if clean_number.startswith("0"):
                clean_number = "+61" + clean_number[1:]
            elif not clean_number.startswith("+"):
                if clean_number.startswith("4"):
                    clean_number = "+61" + clean_number
            
            # ASYNC TWILIO CALL
            auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
            data = {
                "To": clean_number,
                "From": from_number,
                "Body": message
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data, auth=auth)
                response.raise_for_status()
                msg_data = response.json()
                
            logger.info(f"SMS sent to {mask_phone(clean_number)} from {mask_phone(from_number)}: {msg_data.get('sid')}")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_number}: {e}")
            return False

sms_service = SmsService()
