from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Ovela AI Backend"

    # Meta (WhatsApp)
    META_APP_ID: str = "" # App ID
    META_ACCESS_TOKEN: str
    META_PHONE_NUMBER_ID: str
    META_VERIFY_TOKEN: str

    # OpenAI
    OPENAI_API_KEY: str

    # Appwrite
    APPWRITE_ENDPOINT: str = "https://syd.cloud.appwrite.io/v1"
    APPWRITE_PROJECT_ID: str
    APPWRITE_API_KEY: str

    # Resend
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "hello@ovela.dev"

    # Twilio (Missed Call → WhatsApp)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""  # Your purchased Twilio number

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"

settings = Settings()
