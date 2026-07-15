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

import sentry_sdk

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        send_default_pii=True,
        traces_sample_rate=1.0,  # Capture 100% of traces for hackathon baseline
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
    """Production payment success page — surfaced after Stripe checkout completes."""
    booking_ref = request.query_params.get("ref", "")
    ref_html = f'<div class="ref">Booking Reference: <strong>{booking_ref}</strong></div>' if booking_ref else ""
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex">
  <title>Payment Confirmed — Coal Creek Motel</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; padding: 24px;
    }}
    .card {{
      background: #ffffff; border-radius: 24px; padding: 52px 44px;
      max-width: 540px; width: 100%; text-align: center;
      box-shadow: 0 8px 48px rgba(0,0,0,0.10); border: 1px solid #d1fae5;
      animation: fadeUp 0.5s ease;
    }}
    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(16px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}
    .icon-wrap {{
      width: 80px; height: 80px; background: #d1fae5; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 32px; font-size: 40px;
      box-shadow: 0 0 0 8px #ecfdf5;
    }}
    h1 {{ font-size: 28px; font-weight: 700; color: #111827; margin-bottom: 12px; letter-spacing: -0.02em; }}
    .subtitle {{ font-size: 17px; color: #4b5563; line-height: 1.6; margin-bottom: 8px; }}
    .next-steps {{
      margin-top: 28px; padding: 20px 24px;
      background: #f9fafb; border-radius: 14px; border: 1px solid #e5e7eb;
      text-align: left;
    }}
    .next-steps p {{ font-size: 14px; color: #374151; margin-bottom: 8px; line-height: 1.5; }}
    .next-steps p:last-child {{ margin-bottom: 0; }}
    .next-steps strong {{ color: #111827; }}
    .ref {{
      display: inline-block; margin-top: 24px; padding: 12px 28px;
      background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 12px;
      font-size: 15px; color: #065f46; font-weight: 600; letter-spacing: 0.01em;
    }}
    .footer {{ margin-top: 32px; font-size: 12px; color: #9ca3af; }}
    .footer a {{ color: #9ca3af; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon-wrap">✅</div>
    <h1>Payment Confirmed</h1>
    <p class="subtitle">Your booking at <strong>Coal Creek Motel</strong> is confirmed.</p>
    <p class="subtitle">A confirmation email with your booking details is on its way.</p>
    {ref_html}
    <div class="next-steps">
      <p><strong>What happens next?</strong></p>
      <p>📧 Check your inbox for a confirmation email with your full booking summary.</p>
      <p>📞 Questions? Call us on <strong>(03) 5166 0244</strong> — we're open 8am–8pm daily.</p>
    </div>
    <p class="footer">Powered by <a href="https://ovela.ai">Ovela AI</a> &mdash; Coal Creek Motel</p>
  </div>
</body>
</html>""")



@app.get("/payment-cancel", response_class=HTMLResponse)
async def payment_cancel(request: Request):
    """Production payment cancel/incomplete page — surfaced when user exits Stripe checkout."""
    booking_ref = request.query_params.get("ref", "")
    ref_note = f"(Reference: {booking_ref})" if booking_ref else ""
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex">
  <title>Payment Incomplete — Coal Creek Motel</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; padding: 24px;
    }}
    .card {{
      background: #ffffff; border-radius: 24px; padding: 52px 44px;
      max-width: 540px; width: 100%; text-align: center;
      box-shadow: 0 8px 48px rgba(0,0,0,0.10); border: 1px solid #fed7aa;
      animation: fadeUp 0.5s ease;
    }}
    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(16px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}
    .icon-wrap {{
      width: 80px; height: 80px; background: #fee2e2; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 32px; font-size: 40px;
      box-shadow: 0 0 0 8px #fff7ed;
    }}
    h1 {{ font-size: 28px; font-weight: 700; color: #111827; margin-bottom: 12px; letter-spacing: -0.02em; }}
    .subtitle {{ font-size: 17px; color: #4b5563; line-height: 1.6; margin-bottom: 8px; }}
    .warning {{
      margin-top: 28px; padding: 20px 24px;
      background: #fff7ed; border: 1px solid #fed7aa; border-radius: 14px;
      font-size: 14px; color: #92400e; line-height: 1.6; text-align: left;
    }}
    .warning strong {{ color: #7c2d12; }}
    .actions {{ margin-top: 28px; display: flex; flex-direction: column; gap: 12px; }}
    .btn {{
      display: block; width: 100%; padding: 14px 24px; border-radius: 12px;
      font-size: 15px; font-weight: 600; text-decoration: none; cursor: pointer;
      transition: opacity 0.15s ease;
    }}
    .btn:hover {{ opacity: 0.85; }}
    .btn-primary {{ background: #111827; color: #ffffff; }}
    .footer {{ margin-top: 32px; font-size: 12px; color: #9ca3af; }}
    .footer a {{ color: #9ca3af; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon-wrap">⏳</div>
    <h1>Payment Not Completed</h1>
    <p class="subtitle">Your room hold is still active — payment was not received.</p>
    <p class="subtitle" style="font-size:13px;color:#9ca3af">{ref_note}</p>
    <div class="warning">
      <strong>Your payment link is valid for 24 hours.</strong><br><br>
      Check your email for the original payment link, or call us directly
      to complete the booking with a staff member.<br><br>
      <strong>Coal Creek Motel &mdash; (03) 5166 0244</strong><br>
      Open daily 8:00 AM &ndash; 8:00 PM
    </div>
    <div class="actions">
      <a href="tel:+61351660244" class="btn btn-primary">📞 Call to Complete Booking</a>
    </div>
    <p class="footer">Powered by <a href="https://ovela.ai">Ovela AI</a> &mdash; Coal Creek Motel</p>
  </div>
</body>
</html>""")
