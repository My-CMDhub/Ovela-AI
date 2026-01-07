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
from services.voice_agent import VoiceAgentHandler
from services.appwrite import db_service
from services.email import email_service
from services.magic_links import generate_demo_approval_url, verify_action_token
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
    Handles demo request from website form.
    - Whitelisted phones: Immediate call (bypass approval)
    - Regular phones: Creates pending lead, sends approval email to team
    """
    if not request.consent:
        raise HTTPException(status_code=400, detail="Consent required")
    
    # Rate Limit Check (whitelisted phones bypass this)
    if not db_service.check_demo_limit(request.phone):
        raise HTTPException(
            status_code=429, 
            detail="Thanks for your interest! You've already tried our demo today. Feel free to request another demo tomorrow, or contact us directly."
        )
    
    # Create demo lead in database
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

    # ============================================================
    # WHITELISTED PHONES: Immediate call (bypass approval)
    # ============================================================
    if is_whitelisted(request.phone):
        logger.info(f"Whitelisted phone {request.phone} - immediate call")
        try:
            call = _trigger_demo_call(request.name, request.business_name, request.phone)
            
            if lead_id:
                db_service.update_demo_lead(lead_id=lead_id, data={"status": "called", "call_sid": call.sid})
            
            return {"status": "success", "call_sid": call.sid, "message": "Calling you now..."}
        except Exception as e:
            logger.error(f"Failed to initiate call: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    # ============================================================
    # REGULAR PHONES: Pending approval flow
    # ============================================================
    if lead_id:
        # Update status to pending_approval
        db_service.update_demo_lead(lead_id=lead_id, data={"status": "pending_approval"})
        
        # Generate magic links for approve/reject
        extra_data = {"name": request.name, "phone": request.phone, "business": request.business_name}
        approve_url = generate_demo_approval_url(lead_id, "demo-approve", extra_data)
        reject_url = generate_demo_approval_url(lead_id, "demo-reject", extra_data)
        
        # Send approval email to team in background
        background_tasks.add_task(
            email_service.send_demo_approval_request,
            {
                "name": request.name,
                "business_name": request.business_name,
                "phone": request.phone,
                "created_at": datetime.now().isoformat(),
                "approve_url": approve_url,
                "reject_url": reject_url
            }
        )
        
        logger.info(f"Demo request {lead_id} pending approval for {request.phone}")
    
    return {
        "status": "pending", 
        "message": "Thanks! Your phone will ring shortly—keep it close."
    }


@router.get("/demo-approve")
async def approve_demo(token: str, background_tasks: BackgroundTasks):
    """
    Approve a demo request via magic link.
    Triggers the Twilio call to the user.
    """
    # Verify the magic link token
    is_valid, payload, error_msg = verify_action_token(token)
    
    if not is_valid:
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Demo Approval</title></head>
            <body style="font-family: system-ui; padding: 40px; text-align: center;">
                <h1>⚠️ Link Invalid</h1>
                <p>{error_msg}</p>
            </body>
            </html>
            """,
            status_code=400
        )
    
    lead_id = payload.get("identifier")
    extra = payload.get("extra", {})
    phone = extra.get("phone")
    name = extra.get("name", "there")
    business = extra.get("business", "your business")
    
    if not phone:
        return HTMLResponse(
            content="""
            <html>
            <head><title>Demo Approval</title></head>
            <body style="font-family: system-ui; padding: 40px; text-align: center;">
                <h1>❌ Error</h1>
                <p>Missing phone number in token. Please check the dashboard.</p>
            </body>
            </html>
            """,
            status_code=400
        )
    
    # Check if already processed
    try:
        lead = db_service.get_demo_lead(lead_id)
        if lead and lead.get("status") in ["called", "approved", "rejected"]:
            status = lead.get("status")
            return HTMLResponse(
                content=f"""
                <html>
                <head><title>Demo Approval</title></head>
                <body style="font-family: system-ui; padding: 40px; text-align: center;">
                    <h1>ℹ️ Already Processed</h1>
                    <p>This demo request was already {status}.</p>
                </body>
                </html>
                """
            )
    except Exception as e:
        logger.warning(f"Could not check lead status: {e}")
    
    # Trigger the call
    try:
        call = _trigger_demo_call(name, business, phone)
        
        # Update lead status
        db_service.update_demo_lead(lead_id=lead_id, data={
            "status": "called",
            "call_sid": call.sid,
            "approved_at": datetime.now().isoformat()
        })
        
        logger.info(f"Demo approved and call triggered for {phone}")
        
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Demo Approved</title></head>
            <body style="font-family: system-ui; padding: 40px; text-align: center;">
                <h1>✅ Demo Approved!</h1>
                <p>Calling <strong>{name}</strong> at <strong>{phone}</strong> now.</p>
                <p style="color: #666; margin-top: 20px;">You can close this tab.</p>
            </body>
            </html>
            """
        )
        
    except Exception as e:
        logger.error(f"Failed to trigger demo call: {e}")
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Demo Approval</title></head>
            <body style="font-family: system-ui; padding: 40px; text-align: center;">
                <h1>❌ Call Failed</h1>
                <p>Could not initiate call: {str(e)}</p>
                <p>Please try calling manually or check the logs.</p>
            </body>
            </html>
            """,
            status_code=500
        )


@router.get("/demo-reject")
async def reject_demo(token: str):
    """
    Reject a demo request via magic link.
    Updates lead status to rejected.
    """
    # Verify the magic link token
    is_valid, payload, error_msg = verify_action_token(token)
    
    if not is_valid:
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Demo Rejection</title></head>
            <body style="font-family: system-ui; padding: 40px; text-align: center;">
                <h1>⚠️ Link Invalid</h1>
                <p>{error_msg}</p>
            </body>
            </html>
            """,
            status_code=400
        )
    
    lead_id = payload.get("identifier")
    extra = payload.get("extra", {})
    name = extra.get("name", "User")
    
    # Update lead status
    try:
        db_service.update_demo_lead(lead_id=lead_id, data={
            "status": "rejected",
            "rejected_at": datetime.now().isoformat()
        })
        
        logger.info(f"Demo rejected for lead {lead_id}")
        
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Demo Rejected</title></head>
            <body style="font-family: system-ui; padding: 40px; text-align: center;">
                <h1>🚫 Demo Rejected</h1>
                <p>Request from <strong>{name}</strong> has been declined.</p>
                <p style="color: #666; margin-top: 20px;">You can close this tab.</p>
            </body>
            </html>
            """
        )
        
    except Exception as e:
        logger.error(f"Failed to reject demo: {e}")
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Demo Rejection</title></head>
            <body style="font-family: system-ui; padding: 40px; text-align: center;">
                <h1>❌ Error</h1>
                <p>Could not update status: {str(e)}</p>
            </body>
            </html>
            """,
            status_code=500
        )


def _trigger_demo_call(name: str, business_name: str, phone: str):
    """
    Helper function to trigger a Twilio demo call.
    Returns the call object.
    """
    # URL-encode the parameters
    encoded_name = quote(name)
    encoded_business = quote(business_name)
    encoded_phone = quote(phone)
    
    # Construct the TwiML URL
    twiml_url = f"{settings.BACKEND_URL}/api/voice/twiml?name={encoded_name}&business={encoded_business}&phone={encoded_phone}"
    
    call = twilio_client.calls.create(
        to=phone,
        from_=settings.TWILIO_PHONE_NUMBER,
        url=twiml_url,
        record=True
    )
    
    logger.info(f"Triggered demo call to {phone}, SID: {call.sid}")
    return call


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
    transfer_failed = params.get("transfer_failed", "false")
    
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
    stream.parameter(name="transfer_failed", value=transfer_failed)
    
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
    handler = VoiceAgentHandler(websocket)
    
    try:
        await handler.start()
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()
