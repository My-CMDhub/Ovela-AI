from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from api import webhooks, dashboard, twilio

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
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(twilio.router, prefix="/twilio", tags=["twilio"])

@app.get("/")
def read_root():
    return {"message": "Ovela AI Backend is running 🚀"}

