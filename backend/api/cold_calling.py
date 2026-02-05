from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, Response
import logging
import json
import base64
from typing import Optional

from services.cold_calling.service import ColdCallService, call_manager
from services.cold_calling.prompts import get_prompt
# Import your LLM service here. For now I'll mock or reuse existing.
# I'll reuse the architecture from voice_agent if possible, but for "isolation" 
# I will implement a minimal loop using OpenAI directly or the 'voice_agent' generic helpers if available.
# To ensure "Super Fast", a tight loop here is best.
# I'll assume we can use `services.voice_agent.core.llm` or similar if I can find it.
# CHECK: `backend/services/voice_agent/llm.py`? 
# For now, I'll stub the LLM interaction in the websocket loop to get the plumbing working.

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/trigger")
async def trigger_cold_call(
    request: Request,
    to: str,
    business_name: str,
    pms: str = "PMS",
    mode: str = "sales",
    prank_type: str = "theft"
):
    """
    Trigger an outbound cold call.
    """
    try:
        call_sid = await ColdCallService.start_call(to, business_name, pms, mode, prank_type)
        return {"status": "initiated", "call_sid": call_sid}
    except Exception as e:
        logger.error(f"Failed to trigger call: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/twiml/connect")
async def get_connect_twiml(
    request: Request,
    business_name: str = "Partner",
    pms: str = "PMS",
    mode: str = "sales",
    prank_type: str = "theft"
):
    """
    Returns TwiML to start the Media Stream.
    Passing metadata as custom parameters to the stream.
    """
    # Dynamically determine WSS URL from the request base URL
    # This ensures it works with ngrok or deployed domains without hardcoding
    base = str(request.base_url).rstrip("/")
    if base.startswith("https"):
        ws_base = base.replace("https://", "wss://")
    else:
        ws_base = base.replace("http://", "ws://")
        
    stream_url = f"{ws_base}/api/cold-calling/stream"
    
    # Construct TwiML
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="business_name" value="{business_name}" />
            <Parameter name="pms" value="{pms}" />
            <Parameter name="mode" value="{mode}" />
            <Parameter name="prank_type" value="{prank_type}" />
        </Stream>
    </Connect>
</Response>
"""
    return Response(content=xml, media_type="application/xml")

@router.websocket("/observe/{call_id}")
async def observe_call(websocket: WebSocket, call_id: str):
    """
    Frontend connects here to listen to the call.
    """
    await websocket.accept()
    await call_manager.register_observer(call_id, websocket)
    try:
        while True:
            # Keep alive / receive commands from frontend (maybe 'hangup'?)
            data = await websocket.receive_text()
            # Handle commands if needed
    except WebSocketDisconnect:
        logger.info(f"Observer disconnected for {call_id}")
        # Cleanup done in manager if needed, or strict 'del'
    except Exception as e:
        logger.error(f"Observer error: {e}")

@router.websocket("/stream")
async def twilio_stream(websocket: WebSocket):
    """
    Handle Twilio Media Stream.
    Uses the ColdCallHandler to bridge Deepgram and Observer.
    """
    await websocket.accept()
    
    from services.cold_calling.handler import ColdCallHandler
    handler = ColdCallHandler(websocket)
    await handler.start()


