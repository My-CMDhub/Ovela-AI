from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Ovela AI Backend"
    BACKEND_URL: str = "https://ovela-12c561a30285.herokuapp.com"  # Production URL

    # Meta (WhatsApp Cloud API)
    META_ACCESS_TOKEN: str = ""
    META_PHONE_NUMBER_ID: str = ""
    META_VERIFY_TOKEN: str = ""  # For incoming webhooks
    WHATSAPP_TEMPLATE_NAME: str = "saranda_approval_v1"

    # OpenAI
    OPENAI_API_KEY: str

    # Appwrite
    APPWRITE_ENDPOINT: str = "https://api.ovela.dev/v1"
    APPWRITE_PROJECT_ID: str
    APPWRITE_API_KEY: str

    # Optional Security Keys
    DASHBOARD_API_KEY: Optional[str] = None  # Internal key for dashboard access

    # Resend
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "hello@ovela.dev"
    # Comma-separated list of emails to receive demo alerts
    DEMO_ALERT_RECIPIENTS: str = "demo@ovela.dev"
    # Comma-separated list of emails for staff notifications (callbacks, approvals)
    STAFF_NOTIFICATION_RECIPIENTS: str = "officialcoalcreek@gmail.com"

    # Twilio (Missed Call → WhatsApp)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = "+61348236219"  # Your purchased Twilio number
    TWILIO_WHATSAPP_NUMBER: str = "+14155238886"  # Twilio WhatsApp Sandbox number
    
    # Saranda Restaurant Staff WhatsApp
    SARANDA_STAFF_WHATSAPP: str = "+61475677771"  # Test: your number | Prod: +61452557167
    
    # WhatsApp Button Support (hybrid approach)
    USE_WHATSAPP_BUTTONS: bool = True  # True = buttons (testing), False = text (production)

    # Deepgram
    DEEPGRAM_API_KEY: str
    
    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = ""
    STRIPE_WEBHOOK_SECRET: Optional[str] = ""
    
    # Staff Phone (for transfers)
    STAFF_PHONE_NUMBER: str = "+61492897718"
    
    # Demo Settings
    TENANT_ID: str = "coalcreek"  # Default tenant (coalcreek is production)
    TRANSFER_TIMEOUT: int = 10  # Seconds before fallback to AI

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"

Settings.model_rebuild()
settings = Settings()
