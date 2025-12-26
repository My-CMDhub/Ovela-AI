import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from api import chat, dashboard, twilio, motel, voice, notifications, actions

# Configure logging to show in console
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(name)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

app = FastAPI(title=settings.PROJECT_NAME)

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
app.include_router(chat.router, prefix="/webhooks", tags=["chat"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(twilio.router, prefix="/twilio", tags=["twilio"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])
app.include_router(motel.router, tags=["motel"])
app.include_router(notifications.router, prefix="/api", tags=["notifications"])
app.include_router(actions.router, prefix="/api", tags=["actions"])

@app.get("/")
def read_root():
    return {"message": "Ovela AI Backend is running 🚀"}

