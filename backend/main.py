import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from api import twilio, voice, notifications, actions, stripe
# NOTE: WhatsApp chat agent and dashboard were deleted
# from api import chat, dashboard

# Initialize New Relic BEFORE creating FastAPI app
import newrelic.agent
newrelic.agent.initialize('newrelic.ini')

MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
LOG_FILE_PATH = Path(__file__).resolve().parent / "logs" / "logs.txt"
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)


class MelbourneFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, MELBOURNE_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()


# Configure logging to show in console + persist in backend/logs/logs.txt
log_format = "%(asctime)s %(levelname)s:     %(name)s - %(message)s"
formatter = MelbourneFormatter(log_format)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

file_handler = logging.FileHandler(LOG_FILE_PATH, mode="a", encoding="utf-8")
file_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[stream_handler, file_handler],
    force=True,
)

# Create FastAPI app (New Relic auto-instruments ASGI apps)
app = FastAPI(title=settings.PROJECT_NAME)

# Scheduler for background jobs
from services.scheduled_jobs.scheduler import start_scheduler, shutdown_scheduler

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    mel_time = datetime.now(MELBOURNE_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    logging.info("=" * 72)
    logging.info(f"🧪 LOG SESSION START | Melbourne time: {mel_time}")
    logging.info("=" * 72)
    logging.info("🚀 Starting Coal Creek CRM backend...")
    # start_scheduler() # Disabled to eliminate background noise/latency (Saranda legacy)
    logging.info("✅ Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    mel_time = datetime.now(MELBOURNE_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    logging.info("-" * 72)
    logging.info(f"🛑 LOG SESSION END | Melbourne time: {mel_time}")
    logging.info("-" * 72)
    logging.info("🛑 Shutting down application...")
    shutdown_scheduler()
    logging.info("✅ Application shutdown complete")

# CORS middleware for dashboard frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://ovela.dev",
        "https://www.ovela.dev",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
# NOTE: WhatsApp chat agent and dashboard were deleted (frozen)
# app.include_router(chat.router, prefix="/webhooks", tags=["chat"])
# app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(twilio.router, prefix="/twilio", tags=["twilio"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])

# Refactored: 'motel' is now 'dashboard', mounted on both paths for backward compatibility
from api import dashboard
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(dashboard.router, prefix="/api/motel", tags=["motel_legacy"]) # Legacy support (webhooks)

# Fix: Mount notifications under /api/motel so proxy works (dashboard/notifications -> motel/notifications)
app.include_router(notifications.router, prefix="/api/dashboard", tags=["notifications"]) 
app.include_router(notifications.router, prefix="/api/motel", tags=["notifications_legacy"])

# Original mounts 
app.include_router(notifications.router, prefix="/api", tags=["notifications_root"])
app.include_router(actions.router, prefix="/api", tags=["actions"])
app.include_router(stripe.router, prefix="/api", tags=["stripe"])


@app.get("/")
def read_root():
    return {"message": "Ovela AI Backend is running 🚀"}

