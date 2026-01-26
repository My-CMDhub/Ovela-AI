from twilio.rest import Client
import logging
from core.config import settings

logger = logging.getLogger(__name__)

class SmsService:
    def __init__(self):
        self.client = None
        self.from_number = settings.TWILIO_PHONE_NUMBER
        
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
        else:
            logger.warning("Twilio credentials missing - SMS service disabled")

    def send_sms(self, to_number: str, message: str) -> bool:
        """Send an SMS message."""
        if not self.client:
            logger.warning("SMS service not configured - skipping SMS")
            return False
            
        try:
            # Basic phone number cleaning (ensure +61 for AU if missing)
            # Assuming AU numbers for now based on context (Coal Creek, +61 default)
            clean_number = to_number.strip().replace(" ", "")
            if clean_number.startswith("0"):
                clean_number = "+61" + clean_number[1:]
            elif not clean_number.startswith("+"):
                # Default to AU if no country code? Or just try as is?
                # Let's assume +61 if starts with 4 (mobile)
                if clean_number.startswith("4"):
                    clean_number = "+61" + clean_number
            
            msg = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=clean_number
            )
            logger.info(f"SMS sent to {clean_number}: {msg.sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_number}: {e}")
            return False

sms_service = SmsService()
