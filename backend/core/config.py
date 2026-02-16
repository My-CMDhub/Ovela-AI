from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Ovela AI Backend"
    BACKEND_URL: str = "https://ovela-12c561a30285.herokuapp.com"  
    ENVIRONMENT: str = "demo"  # 'demo' or 'production'
    TENANT_ID: str = "coalcreek"  

    # Meta (WhatsApp Cloud API)
    META_ACCESS_TOKEN: str = ""
    META_PHONE_NUMBER_ID: str = ""
    META_VERIFY_TOKEN: str = ""  


    # OpenAI
    OPENAI_API_KEY: str

    # Appwrite
    APPWRITE_ENDPOINT: str = "https://api.ovela.dev/v1"
    APPWRITE_PROJECT_ID: str
    APPWRITE_API_KEY: str

    # Optional Security Keys
    DASHBOARD_API_KEY: Optional[str] = None  # Internal key for dashboard access

    # SMTP
    SMTP_HOST: str = "smtppro.zoho.com.au"
    SMTP_PORT: int = 465
    SMTP_USER: str = "hello@ovela.dev"
    SMTP_PASSWORD: str
    MAIL_FROM: str = "Ovela <hello@ovela.dev>"
    
    # Internal aliases
    MAIL_NOTIFICATIONS: str = "Ovela Notifications <notifications@ovela.dev>"
    MAIL_BOOKINGS: str = "Ovela Bookings <bookings@ovela.dev>"

    # Resend (Deprecated, kept for compatibility if needed)
    RESEND_API_KEY: str = ""
    # Comma-separated list of emails to receive demo alerts
    DEMO_ALERT_RECIPIENTS: str = "hello@ovela.dev"
    # Comma-separated list of emails for staff notifications (callbacks, approvals)
    STAFF_NOTIFICATION_RECIPIENTS: str = "officialcoalcreek@gmail.com"

    # Twilio (Missed Call → WhatsApp)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = "+61468088990"  # my purchased number
    TWILIO_WHATSAPP_NUMBER: str = "+14155238886"  
    

    


    # Deepgram
    DEEPGRAM_API_KEY: str
    
    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = ""
    STRIPE_WEBHOOK_SECRET: Optional[str] = ""
    
    # Staff Phone (for transfers)
    STAFF_PHONE_NUMBER: str = "+61475677771"
    
    # Demo Settings
    TRANSFER_TIMEOUT: int = 10  # Seconds before fallback to AI
    
    # Phone to Tenant Mapping (Ingress)
    # Maps Twilio 'To' number -> Tenant ID (Can be set via env var as JSON)
    PHONE_TO_TENANT_MAP: dict = {}

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"

Settings.model_rebuild()
settings = Settings()
