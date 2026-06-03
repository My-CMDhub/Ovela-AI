"""
ADK Graph API Router — Ovela AI Cold Path Webhook.

Exposes the Google ADK multi-agent orchestrator over HTTP so that:
- The live Twilio voice handler can POST complex booking queries here
  as fire-and-forget background tasks (Cold Path).
- The ADK session is keyed by call_sid so state is preserved across
  multiple tool calls within the same Twilio call.

Architecture:
    Deepgram tool webhook → CoalCreekFunctionDispatcher
    CoalCreekFunctionDispatcher → asyncio.create_task(POST /api/adk/query)
    ADKOrchestrator (Cold Path) → BookingWorker / InfoWorker → response stored

The singleton ADKOrchestrator is injected via FastAPI dependency so it is
created once on startup and reused across all requests.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ADKQueryRequest(BaseModel):
    """Incoming ADK query from the voice handler cold-path dispatch."""
    call_sid: str = Field(..., description="Twilio CallSid — used as ADK user_id for session isolation")
    query: str = Field(..., description="User's transcribed utterance or booking intent")
    session_state: Optional[dict] = Field(
        default=None,
        description="Optional state to merge into the ADK session (e.g., caller name, dates)"
    )


class ADKQueryResponse(BaseModel):
    """Response from the ADK orchestrator graph."""
    call_sid: str
    session_id: str
    response: str
    routed_to: Optional[str] = None  # e.g., "BookingWorker" or "InfoWorker" (future)


# ---------------------------------------------------------------------------
# Dependency: Singleton ADK Orchestrator
# ---------------------------------------------------------------------------

def get_adk_orchestrator():
    """
    Dependency that returns the singleton ADKOrchestrator from app state.

    The orchestrator is created once in main.py startup_event and stored in
    app.state.adk_orchestrator. This avoids re-instantiating agents on every
    request (expensive LlmAgent construction) and preserves InMemorySession
    state across multiple calls within the same Twilio call.
    """
    from fastapi import Request
    # Late import to avoid circular imports
    from main import app as _app
    orchestrator = getattr(_app.state, "adk_orchestrator", None)
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="ADK Orchestrator not initialised. Backend may still be starting up."
        )
    return orchestrator


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/query", response_model=ADKQueryResponse, tags=["adk"])
async def adk_query(request: ADKQueryRequest):
    """
    Route a user query through the Gemini ADK multi-agent graph.

    Cold Path: This endpoint is called asynchronously from the voice handler
    as a background task. The Twilio/Deepgram audio stream continues unblocked
    while this runs.

    Session State:
        - Each call_sid maps to a unique, isolated ADK session.
        - Sessions persist across multiple POST requests within the same call.
        - Optional session_state dict is merged on each call.
    """
    # Late import inside request to avoid circular at module load time
    from services.adk.graph import ADKOrchestrator
    from main import app as _app

    orchestrator: ADKOrchestrator = getattr(_app.state, "adk_orchestrator", None)
    if orchestrator is None:
        logger.error("❌ ADK: Orchestrator not found in app.state — startup may have failed")
        raise HTTPException(status_code=503, detail="ADK Orchestrator unavailable")

    call_sid = request.call_sid
    query = request.query.strip()

    if not query:
        raise HTTPException(status_code=422, detail="Query text cannot be empty")

    logger.info("🤖 ADK /query: call_sid=%s | query='%s...'", call_sid[:8], query[:50])

    try:
        # Get or create isolated session for this Twilio call
        session = await orchestrator.get_or_create_session(user_id=call_sid)
        session_id = session.id

        # Optionally merge caller state (name, dates) into session
        if request.session_state:
            await orchestrator.update_session_state(
                user_id=call_sid,
                session_id=session_id,
                state=request.session_state,
            )

        # Run the ADK graph — Manager routes to BookingWorker or InfoWorker
        response_text = await orchestrator.query(
            user_id=call_sid,
            session_id=session_id,
            text=query,
        )

        logger.info(
            "🤖 ADK /query done: call_sid=%s | response_len=%d",
            call_sid[:8],
            len(response_text),
        )

        return ADKQueryResponse(
            call_sid=call_sid,
            session_id=session_id,
            response=response_text,
        )

    except Exception as exc:
        logger.error("❌ ADK /query error for %s: %s", call_sid[:8], exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"ADK graph error: {exc}")


@router.get("/health", tags=["adk"])
async def adk_health():
    """
    Quick health check — confirms ADKOrchestrator is live.
    Used by judging demo to show the Cold Path is active.
    """
    from main import app as _app
    orchestrator = getattr(_app.state, "adk_orchestrator", None)
    if orchestrator is None:
        return {"status": "unavailable", "message": "ADK Orchestrator not yet initialised"}
    return {
        "status": "ok",
        "agents": ["OvelaManager", "BookingWorker", "InfoWorker"],
        "model": "gemini-2.5-flash",
        "session_backend": "InMemorySessionService",
    }
