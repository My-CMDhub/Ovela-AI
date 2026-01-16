from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Ovela AI Backend"
    BACKEND_URL: str = "https://ovela-12c561a30285.herokuapp.com"  # Production URL

    # Meta (WhatsApp)
    META_APP_ID: str = "" # App ID
    META_ACCESS_TOKEN: str
    META_PHONE_NUMBER_ID: str
    META_VERIFY_TOKEN: str

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
    STAFF_NOTIFICATION_RECIPIENTS: str = "getnewone2022@gmail.com"

    # Twilio (Missed Call → WhatsApp)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = "+61348236219"  # Your purchased Twilio number

    # Deepgram
    DEEPGRAM_API_KEY: str = ""
    
    # Call Transfer Settings
    STAFF_PHONE_NUMBER: str = "+61493291626"  # Reception for call transfers
    TRANSFER_TIMEOUT: int = 10  # Seconds before fallback to AI
    
    # Validation/Demo Settings
    TENANT_ID: str = "lydoun" # lydoun, paddlesteamer

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"

Settings.model_rebuild()
settings = Settings()
