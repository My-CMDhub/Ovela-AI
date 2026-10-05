import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Ovela AI Backend"
    BACKEND_URL: str = os.getenv("BACKEND_URL", "https://ovela-12c561a30285.herokuapp.com")
    ENVIRONMENT: str = "demo"  # 'demo' or 'production'
    TENANT_ID: str = "coalcreek"  
    USE_LIVE_SCRAPING: bool = False  # Toggle between Appwrite PMS vs live scraping
    VOICE_PIPELINE_MODE: str = "cascaded"  # 'cascaded' (sub-second Phase 12) or 'monolithic'

    # Observability (Sentry)
    SENTRY_DSN: str = ""  # set via env; empty disables Sentry (main.py guards on it)

    # Meta (WhatsApp Cloud API)
    META_ACCESS_TOKEN: str = ""
    META_PHONE_NUMBER_ID: str = ""
    META_VERIFY_TOKEN: str = ""  


    # OpenAI
    OPENAI_API_KEY: str
    # Live-call deadlines for each model round (see CascadedPipelineOrchestrator
    # ._open_llm_round). Conservative on purpose: a normal first token is
    # ~0.5 s and a tool round ~1.1-1.7 s, so these only fire on a real stall.
    LLM_FIRST_TOKEN_TIMEOUT_S: float = 6.0
    LLM_STREAM_GAP_TIMEOUT_S: float = 10.0
    # Model for the one retry after a missed first token; empty = same model.
    LLM_FALLBACK_MODEL: str = ""
    
    # Start the first model round on Deepgram Flux's EagerEndOfTurn and keep it
    # if EndOfTurn confirms the same words (see CascadedPipelineOrchestrator
    # ._start_speculation). Off by default: it spends tokens on every eager
    # turn the caller then carries on from. A tenant can override it with
    # voice_settings.speculative_eot.
    SPECULATIVE_EOT_ENABLED: bool = False

    # Cartesia (Direct TTS Bypass)
    CARTESIA_API_KEY: Optional[str] = ""

    # Appwrite
    APPWRITE_ENDPOINT: str = "https://api.ovela.dev/v1"
    APPWRITE_PROJECT_ID: str
    APPWRITE_API_KEY: str

    # Optional Security Keys
    DASHBOARD_API_KEY: Optional[str] = None  # Internal key for dashboard access

    # Off during testing so a live call does not fill a real inbox. Every
    # other code path behaves exactly as if the send had succeeded.
    EMAIL_ENABLED: bool = True

    # SMTP (Ovela - Zoho)
    SMTP_HOST: str = "smtppro.zoho.com.au"
    SMTP_PORT: int = 465
    SMTP_USER: str = "bookings@ovela.dev"
    SMTP_PASSWORD: str
    MAIL_FROM: str = "Ovela <hello@ovela.dev>"

    # SMTP (Coal Creek Motel - Gmail)
    GMAIL_SMTP_HOST: str = "smtp.gmail.com"
    GMAIL_SMTP_PORT: int = 587
    GMAIL_SMTP_USER: str = "officialcoalcreek@gmail.com"
    COALCREEK_APP_PASSWORD: str = ""

    # Internal aliases
    MAIL_NOTIFICATIONS: str = "Ovela Notifications <notifications@ovela.dev>"
    MAIL_BOOKINGS: str = "Coal Creek Motel <officialcoalcreek@gmail.com>"

    # Resend (Deprecated, kept for compatibility if needed)
    RESEND_API_KEY: str = ""
    # Comma-separated list of emails to receive demo alerts
    DEMO_ALERT_RECIPIENTS: str = "hello@ovela.dev"
    # Comma-separated list of emails for staff notifications (callbacks, approvals)
    STAFF_NOTIFICATION_RECIPIENTS: str = "officialcoalcreek@gmail.com"

    # Twilio (Missed Call → WhatsApp)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""  # set via env

    # Inbound authentication for Twilio traffic. Each is "off" | "report" |
    # "enforce". "report" only logs (and alerts Sentry) on a missing/invalid
    # credential and lets the call through, so the checks can ship without
    # risking a real call; flip to "enforce" once the logs show verdict=valid
    # on live calls. Unknown values behave as "report".
    #  - STREAM_AUTH_MODE: the signed `stream_token` <Parameter> that ties a
    #    Media Stream socket to the TwiML we issued (core/stream_auth.py).
    #  - TWILIO_SIGNATURE_MODE: X-Twilio-Signature on the Twilio webhooks
    #    (core/twilio_signature.py). Needs TWILIO_AUTH_TOKEN.
    # The stream token is only as strong as the webhook that hands it out:
    # an unsigned /twilio/voice will mint a token for any From. Enforce both.
    STREAM_AUTH_MODE: str = "report"
    TWILIO_SIGNATURE_MODE: str = "report"
    # Optional. Unset -> derived from the magic-link secret (domain-separated).
    STREAM_TOKEN_SECRET: str = ""
    # Seconds a Media Stream socket may stay open without sending `start`.
    # The Deepgram and Cartesia sockets are opened before Twilio's first
    # message, so a client that connects and goes quiet would otherwise hold
    # both (and their billing) open indefinitely. Twilio sends `connected` and
    # `start` within milliseconds, so 10 s only ever catches a stalled client.
    STREAM_START_TIMEOUT_S: float = 10.0


    # Personal Assistant Target Number
    MY_NUMBER: Optional[str] = None

    # Deepgram
    DEEPGRAM_API_KEY: str
    
    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = ""
    STRIPE_WEBHOOK_SECRET: Optional[str] = ""
    
    # Staff Phone (for transfers)
    STAFF_PHONE_NUMBER: str = ""  # set via env
    
    # Demo Settings
    # Seconds the staff phone rings on a transfer before the caller is handed
    # back to the AI (and a callback request is recorded). 10s is only ~2-3
    # rings — short on purpose so nobody waits in silence, but tunable via env
    # (TRANSFER_TIMEOUT=20) if staff need longer to reach the phone.
    TRANSFER_TIMEOUT: int = 10
    
    # Phone to Tenant Mapping (Ingress)
    # Maps Twilio 'To' number -> Tenant ID (Can be set via env var as JSON)
    PHONE_TO_TENANT_MAP: dict = {
        "+61348236219": "coalcreek"
    }

    class Config:
        case_sensitive = True
        import os
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        extra = "ignore"

Settings.model_rebuild()
settings = Settings()
