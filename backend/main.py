import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from core.config import settings
from api import twilio, voice, notifications, actions, stripe, adk as adk_api, evaluations as evaluations_api


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
    # start_scheduler() # Disabled to eliminate background noise/latency

    # =========================================================================
    # ADK ORCHESTRATOR — Singleton Cold Path Agent Graph
    # Instantiate once on startup; reused across all Twilio calls.
    # Each call_sid gets an isolated InMemory session — no cross-contamination.
    # =========================================================================
    try:
        from services.adk.graph import ADKOrchestrator
        app.state.adk_orchestrator = ADKOrchestrator()
        logging.info("🤖 ADKOrchestrator ready — Cold Path online")
    except Exception as adk_err:
        logging.error(f"❌ ADKOrchestrator failed to initialise: {adk_err}")
        app.state.adk_orchestrator = None  # Graceful degradation

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
app.include_router(adk_api.router, prefix="/api/adk", tags=["adk"])
app.include_router(evaluations_api.router, prefix="/api/motel", tags=["evaluations"])
app.include_router(evaluations_api.router, prefix="/api/dashboard", tags=["evaluations_dashboard"])


@app.get("/")
def read_root():
    return {"message": "Ovela AI Backend is running 🚀"}


@app.get("/payment-success", response_class=HTMLResponse)
async def payment_success(request: Request):
    """Professional payment success page for Stripe redirect."""
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Payment Successful — Coal Creek Motel</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f5f5f7; display: flex; align-items: center;
           justify-content: center; min-height: 100vh; padding: 24px; }
    .card { background: #fff; border-radius: 20px; padding: 48px 40px;
            max-width: 520px; width: 100%; text-align: center;
            box-shadow: 0 4px 32px rgba(0,0,0,0.08); }
    .icon { width: 72px; height: 72px; background: #d1fae5; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            margin: 0 auto 28px; font-size: 36px; }
    h1 { font-size: 26px; font-weight: 700; color: #111827; margin-bottom: 14px;
         letter-spacing: -0.02em; }
    p  { font-size: 16px; color: #6b7280; line-height: 1.6; margin-bottom: 10px; }
    .ref { display: inline-block; margin-top: 24px; padding: 12px 24px;
           background: #f3f4f6; border-radius: 10px; font-size: 14px;
           color: #374151; font-weight: 500; }
    .footer { margin-top: 36px; font-size: 12px; color: #9ca3af; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✅</div>
    <h1>Payment Confirmed</h1>
    <p>Your booking at <strong>Coal Creek Motel</strong> is now confirmed.</p>
    <p>A confirmation email has been sent to your inbox with all booking details.</p>
    <div class="ref">Check your email for your booking reference</div>
    <p class="footer">Powered by Ovela AI &mdash; Coal Creek Motel</p>
  </div>
</body>
</html>""")


@app.get("/payment-cancel", response_class=HTMLResponse)
async def payment_cancel(request: Request):
    """Professional payment cancel page for Stripe redirect."""
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Payment Cancelled — Coal Creek Motel</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f5f5f7; display: flex; align-items: center;
           justify-content: center; min-height: 100vh; padding: 24px; }
    .card { background: #fff; border-radius: 20px; padding: 48px 40px;
            max-width: 520px; width: 100%; text-align: center;
            box-shadow: 0 4px 32px rgba(0,0,0,0.08); }
    .icon { width: 72px; height: 72px; background: #fee2e2; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            margin: 0 auto 28px; font-size: 36px; }
    h1 { font-size: 26px; font-weight: 700; color: #111827; margin-bottom: 14px;
         letter-spacing: -0.02em; }
    p  { font-size: 16px; color: #6b7280; line-height: 1.6; margin-bottom: 10px; }
    .note { display: inline-block; margin-top: 24px; padding: 14px 24px;
            background: #fff7ed; border: 1px solid #fed7aa; border-radius: 10px;
            font-size: 14px; color: #92400e; line-height: 1.5; }
    .footer { margin-top: 36px; font-size: 12px; color: #9ca3af; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">⏰</div>
    <h1>Payment Not Completed</h1>
    <p>Your booking hold is still active, but payment was not received.</p>
    <p>Your payment link expires in <strong>30 minutes</strong> from when it was sent.</p>
    <div class="note">
      Please check your email for the original payment link,<br>
      or call us directly to complete your booking.<br><br>
      <strong>Coal Creek Motel &mdash; (03) 5166 0244</strong>
    </div>
    <p class="footer">Powered by Ovela AI &mdash; Coal Creek Motel</p>
  </div>
</body>
</html>""")

