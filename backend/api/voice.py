from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, BackgroundTasks
from datetime import datetime
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import json
import logging
from urllib.parse import quote
from twilio.twiml.voice_response import VoiceResponse, Connect
from twilio.rest import Client
from core.config import settings
from services.voice_deepgram_agent import DeepgramAgentHandler
from services.appwrite import db_service
from services.email import email_service
from rules.whitelist import is_whitelisted

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Twilio Client
twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

class DemoRequest(BaseModel):
    name: str
    business_name: str
    phone: str
    consent: bool

@router.post("/demo-request")
async def request_demo(request: DemoRequest, background_tasks: BackgroundTasks):
    """
    Initiates an outbound call to the user for the demo.
    """
    if not request.consent:
        raise HTTPException(status_code=400, detail="Consent required")
    
    # Basic validation for +61 (already done in frontend, but good to double check)
    if not request.phone.startswith("+61") and not request.phone.startswith("04"):
         # Allow 04 replacement for testing if needed, or strict +61
         pass

    # Rate Limit Check
    if not db_service.check_demo_limit(request.phone):
        raise HTTPException(
            status_code=429, 
            detail="You have already requested a demo today. Please try again tomorrow."
        )
    
    # Create demo lead in database for tracking
    lead_id = None
    try:
        lead_doc = db_service.create_demo_lead(
            name=request.name,
            business_name=request.business_name,
            phone=request.phone,
            source="website"
        )
        if lead_doc:
            lead_id = lead_doc.get("$id")
            logger.info(f"Created demo lead: {lead_id}")
    except Exception as e:
        logger.warning(f"Failed to create demo lead: {e}")

    try:
        # URL-encode the parameters to handle spaces and special characters
        encoded_name = quote(request.name)
        encoded_business = quote(request.business_name)
        encoded_phone = quote(request.phone)
        
        # Construct the TwiML URL with encoded parameters (including phone)
        twiml_url = f"{settings.BACKEND_URL}/api/voice/twiml?name={encoded_name}&business={encoded_business}&phone={encoded_phone}"
        
        call = twilio_client.calls.create(
            to=request.phone,
            from_=settings.TWILIO_PHONE_NUMBER,
            url=twiml_url,
            record=True # optional
        )
        
        if lead_id:
            try:
                db_service.update_demo_lead(lead_id=lead_id, data={"call_sid": call.sid, "status": "called"})
                logger.info(f"Updated demo lead {lead_id} status to 'called'")
            except Exception as e:
                logger.warning(f"Failed to update demo lead status: {e}")
        
        # Send email alert in background (ONLY for non-whitelisted numbers)
        if not is_whitelisted(request.phone):
            background_tasks.add_task(
                email_service.send_demo_alert,
                {
                    "name": request.name,
                    "business_name": request.business_name,
                    "phone": request.phone,
                    "created_at": datetime.now().isoformat()
                }
            )

        return {"status": "success", "call_sid": call.sid, "message": "Calling you now..."}
    
    except Exception as e:
        logger.error(f"Failed to initiate call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/twiml")
async def get_twiml(request: Request):
    """
    Returns TwiML instructions to connect the call to our WebSocket stream.
    The stream bridges to Deepgram Voice Agent API for STT/LLM/TTS with native VAD.
    """
    params = request.query_params
    user_name = params.get("name", "there")
    business_name = params.get("business", "your business")
    user_phone = params.get("phone", "unknown")
    
    response = VoiceResponse()
    connect = Connect()
    
    # Use Media Stream to bridge to Deepgram Voice Agent API
    host = request.headers.get('host')
    stream = connect.stream(
        url=f"wss://{host}/api/voice/stream"
    )
    
    # Pass custom parameters to the stream
    stream.parameter(name="user_name", value=user_name)
    stream.parameter(name="business_name", value=business_name)
    stream.parameter(name="user_phone", value=user_phone)
    
    response.append(connect)
    response.say("Sorry, I lost the connection. Please try again later.")
    
    return HTMLResponse(content=str(response), media_type="application/xml")


@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Stream.
    Bridges audio to Deepgram Voice Agent API.
    Deepgram handles: STT (flux) + LLM (gpt-4o-mini) + TTS (aura-2) + VAD.
    """
    await websocket.accept()
    handler = DeepgramAgentHandler(websocket)
    
    try:
        await handler.start()
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()
