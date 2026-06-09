from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, BackgroundTasks
from datetime import datetime
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import json
import logging
import asyncio
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
    tenant_id: Optional[str] = "ovela_demo"

@router.post("/demo-request")
async def request_demo(request: DemoRequest, background_tasks: BackgroundTasks):
    """
    Handles demo request from website form.
    - Whitelisted phones: Immediate call (bypass approval)
    - Regular phones: Creates pending lead, sends approval email to team
    """
    if not request.consent:
        raise HTTPException(status_code=400, detail="Consent required")
    
    tenant = request.tenant_id or "ovela_demo"
    # Rate limit (whitelisted numbers bypass)
    if not is_whitelisted(request.phone) and not await db_service.check_demo_limit(
        request.phone, tenant
    ):
        raise HTTPException(
            status_code=429, 
            detail="Thanks for your interest! You've already tried our demo today. Feel free to request another demo tomorrow, or contact us directly."
        )
    
    # Create demo lead in database
    lead_id = None
    try:
        lead_doc = await db_service.create_demo_lead(
            phone=request.phone,
            name=request.name,
            tenant_id=tenant,
            business_name=request.business_name,
            source="website",
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
            call = _trigger_demo_call(request.name, request.business_name, request.phone, request.tenant_id)
            
            if lead_id:
                await db_service.update_demo_lead(lead_id=lead_id, data={"status": "called", "call_sid": call.sid})
            
            return {"status": "success", "call_sid": call.sid, "message": "Calling you now..."}
        except Exception as e:
            logger.error(f"Failed to initiate call: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    # ============================================================
    # REGULAR PHONES: Pending approval flow
    # ============================================================
    if lead_id:
        # Update status to pending_approval
        await db_service.update_demo_lead(lead_id=lead_id, data={"status": "pending_approval"})
        
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
        lead = await db_service.get_demo_lead(lead_id)
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
        # Optimistic locking: Update status FIRST to prevent race conditions
        # If this fails (e.g. 404 or already updated), we catch it and don't trigger call
        updated_lead = await db_service.update_demo_lead(lead_id=lead_id, data={
            "status": "approved", # Temporary status or check
            "approved_at": datetime.now().isoformat()
        })
        
        if not updated_lead:
            # Update failed (likely already processed)
            logger.info(f"Failed to update lead {lead_id} (already processed?) - skipping call")
            return HTMLResponse(
                content=f"""<html><body style="font-family: system-ui; padding: 40px; text-align: center;">
                <h1>ℹ️ Already Processed</h1><p>Request handled.</p></body></html>"""
            )

        # Defaults to ovela_demo for approved website leads
        # If call fails, we should probably revert status, but typically 'approved' is fine
        call = _trigger_demo_call(name, business, phone, tenant_id="ovela_demo", demo_type="brand_rep")
        
        # Update with call SID
        await db_service.update_demo_lead(lead_id=lead_id, data={
            "status": "called",
            "call_sid": call.sid
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
        await db_service.update_demo_lead(lead_id=lead_id, data={
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


def _trigger_demo_call(name: str, business_name: str, phone: str, tenant_id: str = "ovela_demo", demo_type: str = "brand_rep"):
    """
    Helper function to trigger a Twilio demo call.
    Returns the call object.
    """
    # URL-encode the parameters
    encoded_name = quote(name)
    encoded_business = quote(business_name)
    encoded_phone = quote(phone)
    encoded_tenant = quote(tenant_id)
    encoded_demo_type = quote(demo_type)
    
    # Construct the TwiML URL
    twiml_url = f"{settings.BACKEND_URL}/api/voice/twiml?name={encoded_name}&business={encoded_business}&phone={encoded_phone}&tenant_id={encoded_tenant}&demo_type={encoded_demo_type}&is_demo=true"
    
    call = twilio_client.calls.create(
        to=phone,
        from_=settings.TWILIO_PHONE_NUMBER,
        url=twiml_url,
        record=True,
        machine_detection="Enable"
    )
    
    logger.info(f"Triggered demo call to {phone} (tenant={tenant_id}), SID: {call.sid}")
    return call


async def _enable_recording(call_sid: str):
    """Enable recording for an active call via Twilio API (demo calls)."""
    await asyncio.sleep(0.8)  # Let call connect before issuing recording
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: twilio_client.calls(call_sid).recordings.create(recording_channels="mono")
        )
        logger.info(f"⏺️ Recording started for call {call_sid}")
    except Exception as e:
        logger.warning(f"Failed to start recording for {call_sid}: {e}")

@router.post("/twiml")
async def get_twiml(request: Request, background_tasks: BackgroundTasks):
    """
    Returns TwiML instructions to connect the call to our WebSocket stream.
    The stream bridges to Deepgram Voice Agent API for STT/LLM/TTS with native VAD.
    """
    params = request.query_params
    form_data = await request.form()
    user_name = params.get("name", "there")
    business_name = params.get("business", "your business")
    user_phone = params.get("phone") or params.get("From") or form_data.get("From") or "unknown"
    transfer_failed = params.get("transfer_failed", "false")
    tenant_id = params.get("tenant_id", "ovela_demo")
    demo_type = params.get("demo_type", "")
    is_demo = params.get("is_demo", "false")
    
    answered_by = params.get("AnsweredBy", "") or form_data.get("AnsweredBy", "")
    call_sid = params.get("CallSid") or form_data.get("CallSid")

    # Enforce P8 Abuse Prevention & Rate Limiting
    if user_phone != "unknown":
        is_allowed, limit_reason = await db_service.check_voice_rate_limit(user_phone, tenant_id)
        if not is_allowed:
            logger.warning(f"🚫 Call from {user_phone} blocked by rate limiting: {limit_reason}")
            # Log blocked attempt as a transcript record
            await db_service.save_call_transcript(
                tenant_id=tenant_id,
                call_sid=call_sid,
                caller_phone=user_phone,
                transcript=f"[SYSTEM ALERT: Call from {user_phone} blocked by rate limit check. Reason: {limit_reason}]",
                duration=0,
                status="blocked",
                metadata={"reason": limit_reason}
            )
            
            response = VoiceResponse()
            response.say("Thank you for calling. We are currently experiencing high call volumes, or you have reached our call limit. Please try calling back later or visit our website to complete your reservation. Goodbye!", voice="Polly.Nicole")
            response.hangup()
            return HTMLResponse(content=str(response), media_type="application/xml")
    
    # FORCE RECORDING: Ensure all calls (inbound & outbound) are recorded

    if call_sid:
        background_tasks.add_task(_enable_recording, call_sid)
    
    response = VoiceResponse()
    
    # Handle Answering Machines (AMD)
    if "machine" in answered_by.lower():
        logger.info(f"AMD detected machine ({answered_by}) for {user_phone} - leaving message")
        response.say("Hi, this is Ovela. I missed you, but I've sent you an email with the demo details. Chat soon!")
        response.hangup()
        return HTMLResponse(content=str(response), media_type="application/xml")
    
    # Human or Unknown -> Connect to AI Stream
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
    stream.parameter(name="tenant_id", value=tenant_id)
    stream.parameter(name="demo_type", value=demo_type)
    stream.parameter(name="is_demo", value=is_demo)
    
    response.append(connect)
    response.say("Sorry, I lost the connection. Please try again later.")
    
    return HTMLResponse(content=str(response), media_type="application/xml")


@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Stream.
    Bridges audio to Deepgram Voice Agent API.
    Deepgram handles: STT (flux) + LLM (gemini-2.5-flash) + TTS (aura-2) + VAD.
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
