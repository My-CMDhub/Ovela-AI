from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, BackgroundTasks, Depends, Form
from collections import deque
from datetime import datetime
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import html
import json
import logging
import asyncio
import time
from urllib.parse import quote
from twilio.twiml.voice_response import VoiceResponse, Connect
from twilio.rest import Client
from core.config import settings
from core.stream_auth import issue_stream_token
from core.twilio_signature import verify_twilio_signature
from services.voice_agent import VoiceAgentHandler
from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
from services.appwrite import db_service
from services.email import email_service
from services.magic_links import generate_demo_approval_url, verify_action_token
# Same confirm/error pages (and no-store / no-frame headers) as the staff magic
# links: one look, one set of protections, for every link we email.
from api.actions import confirm_page, error_page, _CONFIRM_HEADERS
from rules.whitelist import is_whitelisted
# Phone numbers are PII and logs ship off-box: always log them through mask_phone.
from core.utils import mask_phone

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Twilio Client
twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

class DemoRequest(BaseModel):
    name: str
    business_name: str
    phone: str
    consent: bool
    # Accepted for old clients, but only admin (whitelisted) phones may pick a
    # tenant, and only a known one: see _demo_tenant.
    tenant_id: Optional[str] = "ovela_demo"


DEFAULT_DEMO_TENANT = "ovela_demo"


def _demo_tenant(requested: Optional[str], phone: str) -> str:
    """
    The tenant a demo request runs as.

    /demo-request is a public website form, so the body's tenant_id is attacker
    input. Trusted, it filed leads (and per-phone limit counters, which are kept
    per tenant) under any motel's tenant and, for admin phones, picked which
    motel's agent and data the outbound call used. The website form never sends
    one; it exists so an admin can demo a real motel's agent from their own phone.
    So: admin phones may choose a KNOWN tenant (the demo tenant, the default
    tenant, or one a Twilio number routes to); everyone else, and any unknown
    value, gets the demo tenant.
    """
    known = {DEFAULT_DEMO_TENANT, settings.TENANT_ID, *settings.PHONE_TO_TENANT_MAP.values()}
    if requested and requested in known and is_whitelisted(phone):
        return requested
    return DEFAULT_DEMO_TENANT


# Per-client-IP cap on /demo-request, on top of the per-phone limit. The phone
# limit alone is no limit at all: a script varies the number and every request
# still creates a lead and emails the team an approval request. In-memory and
# per process on purpose (no Redis, no settings): it only has to make abuse
# slow, so N dynos/workers simply allow N x the cap. Generous so real visitors
# never see it, even several behind one carrier-grade NAT: a person tries once
# or twice, and the per-phone limit already stops at 3 an hour.
_DEMO_IP_LIMIT = 20
_DEMO_IP_WINDOW_S = 3600
# Bound memory under a spray of distinct IPs: past this many tracked IPs, drop
# the ones with no hit inside the window.
_DEMO_IP_MAX_TRACKED = 10_000
_demo_ip_hits: dict[str, deque] = {}


def _client_ip(request: Request) -> str:
    """
    The caller's IP behind Heroku's router.

    Heroku APPENDS the address it accepted the connection from to whatever
    X-Forwarded-For the client sent, so only the LAST hop is trustworthy; the
    first is client-typed and a fresh fake per request would reset the limit.
    The website form posts straight to the backend (VoiceDemoForm.tsx uses
    NEXT_PUBLIC_API_URL, no Vercel proxy in between), so that last hop is the
    visitor. request.client is Heroku's router, used only if the header is absent.
    """
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if hops:
        return hops[-1]
    return request.client.host if request.client else "unknown"


def _demo_ip_allowed(ip: str, now: Optional[float] = None) -> bool:
    """Record one request from ip; False once it has used its hourly allowance.
    No await inside, so the check-and-record is atomic on the event loop."""
    now = time.monotonic() if now is None else now
    cutoff = now - _DEMO_IP_WINDOW_S
    hits = _demo_ip_hits.setdefault(ip, deque())
    while hits and hits[0] <= cutoff:
        hits.popleft()
    if len(hits) >= _DEMO_IP_LIMIT:
        return False
    hits.append(now)
    if len(_demo_ip_hits) > _DEMO_IP_MAX_TRACKED:
        for stale in [k for k, v in _demo_ip_hits.items() if not v or v[-1] <= cutoff]:
            del _demo_ip_hits[stale]
    return True


@router.post("/demo-request")
async def request_demo(request: DemoRequest, background_tasks: BackgroundTasks, http_request: Request):
    """
    Handles demo request from website form.
    - Whitelisted phones: Immediate call (bypass approval)
    - Regular phones: Creates pending lead, sends approval email to team
    """
    if not request.consent:
        raise HTTPException(status_code=400, detail="Consent required")

    # Admin phones skip the IP cap like every other demo limit (an office IP
    # running many test calls); nobody can claim one without knowing the list.
    if not is_whitelisted(request.phone) and not _demo_ip_allowed(_client_ip(http_request)):
        raise HTTPException(
            status_code=429,
            detail="We've had a lot of demo requests from your network. Please try again in an hour, or contact us directly."
        )

    tenant = _demo_tenant(request.tenant_id, request.phone)
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
        logger.info(f"Whitelisted phone {mask_phone(request.phone)} - immediate call")
        try:
            call = _trigger_demo_call(request.name, request.business_name, request.phone, tenant)
            
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
        
        logger.info(f"Demo request {lead_id} pending approval for {mask_phone(request.phone)}")
    
    return {
        "status": "pending", 
        "message": "Thanks! Your phone will ring shortly—keep it close."
    }


# GET never acts; POST does (same pattern as api/actions.py). Mail security
# scanners and link previewers fetch every URL in an email on their own, so a
# demo-approve GET that acted placed a real outbound Twilio call to the lead,
# and burned the lead's one-time approval, before anyone on the team clicked.
# The emailed URLs stay GETs (already-sent emails keep working): GET verifies the
# token and renders a confirm page whose button POSTs the token back to the same
# path, where it is verified again and the action runs. GET must stay free of
# db_service and Twilio calls. The token's name/business/phone are what a website
# visitor typed, so every page here HTML-escapes them (they used to go out raw,
# i.e. script in the team's browser).

def _demo_token(token: str, action: str):
    """
    Verify a demo magic-link token for this exact path.

    Returns (payload, None) or (None, error HTMLResponse). The action check stops
    a token minted for one link being replayed on another: the reject link sits
    in the same email, and without it posting that token to /demo-approve placed
    the call. Tokens are minted with action "demo-approve" / "demo-reject"
    (generate_demo_approval_url), so sent emails pass.
    """
    is_valid, payload, error_msg = verify_action_token(token)
    if is_valid and payload.get("action") != action:
        is_valid, error_msg = False, "This link is not valid for this action."
    if not is_valid:
        return None, HTMLResponse(content=error_page("Link Invalid", html.escape(error_msg)), status_code=400)
    return payload, None


@router.get("/demo-approve")
async def confirm_approve_demo(token: str):
    """Confirm page for the demo-approve email link. Verifies only; calls nobody."""
    payload, error = _demo_token(token, "demo-approve")
    if error:
        return error
    extra = payload.get("extra", {})
    if not extra.get("phone"):
        return HTMLResponse(content=error_page("Error", "Missing phone number in token. Please check the dashboard."), status_code=400)
    # Name and business are what a website visitor typed: escape them.
    who = html.escape(f"{extra.get('name', 'there')} ({extra.get('business', 'your business')})")
    message = f"This calls <strong>{who}</strong> at <strong>{html.escape(extra['phone'])}</strong> right away. The link works once."
    return HTMLResponse(content=confirm_page("Approve this demo?", message, "Approve - Call Now", token),
                        headers=_CONFIRM_HEADERS)


@router.get("/demo-reject")
async def confirm_reject_demo(token: str):
    """Confirm page for the demo-reject email link. Verifies only; writes nothing."""
    payload, error = _demo_token(token, "demo-reject")
    if error:
        return error
    name = html.escape(payload.get("extra", {}).get("name", "this lead"))
    message = f"Decline the demo request from <strong>{name}</strong>. No call is made."
    return HTMLResponse(content=confirm_page("Reject this demo?", message, "Reject Demo", token),
                        headers=_CONFIRM_HEADERS)


@router.post("/demo-approve")
async def approve_demo(token: str = Form(...)):
    """
    Approve a demo request via magic link.
    Triggers the Twilio call to the user.
    """
    # Verify the magic link token (again: the GET's check proves nothing here)
    payload, error = _demo_token(token, "demo-approve")
    if error:
        return error
    
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
        
        logger.info(f"Demo approved and call triggered for {mask_phone(phone)}")
        
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Demo Approved</title></head>
            <body style="font-family: system-ui; padding: 40px; text-align: center;">
                <h1>✅ Demo Approved!</h1>
                <p>Calling <strong>{html.escape(name)}</strong> at <strong>{html.escape(phone)}</strong> now.</p>
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
                <p>Could not initiate call: {html.escape(str(e))}</p>
                <p>Please try calling manually or check the logs.</p>
            </body>
            </html>
            """,
            status_code=500
        )


@router.post("/demo-reject")
async def reject_demo(token: str = Form(...)):
    """
    Reject a demo request via magic link.
    Updates lead status to rejected.
    """
    # Verify the magic link token (again: the GET's check proves nothing here)
    payload, error = _demo_token(token, "demo-reject")
    if error:
        return error

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
                <p>Request from <strong>{html.escape(name)}</strong> has been declined.</p>
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
                <p>Could not update status: {html.escape(str(e))}</p>
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
    
    logger.info(f"Triggered demo call to {mask_phone(phone)} (tenant={tenant_id}), SID: {call.sid}")
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

# Twilio fetches this for outbound demo calls (_trigger_demo_call), so it is
# signed like the /twilio webhooks; rejects only in TWILIO_SIGNATURE_MODE=enforce.
@router.post("/twiml", dependencies=[Depends(verify_twilio_signature)])
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
            logger.warning(f"🚫 Call from {mask_phone(user_phone)} blocked by rate limiting: {limit_reason}")
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
        logger.info(f"AMD detected machine ({answered_by}) for {mask_phone(user_phone)} - leaving message")
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
    # Binds the socket to this call's identity; checked on the stream's
    # `start` (core/stream_auth). The library XML-escapes every value.
    stream.parameter(name="stream_token", value=issue_stream_token(call_sid, user_phone, tenant_id))
    
    response.append(connect)
    response.say("Sorry, I lost the connection. Please try again later.")
    
    return HTMLResponse(content=str(response), media_type="application/xml")


@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Stream.
    Bridges audio based on configured VOICE_PIPELINE_MODE setting (`cascaded` or `monolithic`).
    """
    await websocket.accept()
    if getattr(settings, "VOICE_PIPELINE_MODE", "cascaded").lower() == "cascaded":
        logger.info("⚡ [VoiceRoute] Routing Twilio stream to CascadedPipelineOrchestrator")
        orchestrator = CascadedPipelineOrchestrator(websocket)
        try:
            await orchestrator.run_loop()
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error in cascaded orchestrator: {e}")
            await websocket.close()
    else:
        logger.info("🏛️ [VoiceRoute] Routing Twilio stream to monolithic VoiceAgentHandler")
        handler = VoiceAgentHandler(websocket)
        try:
            await handler.start()
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.close()


@router.websocket("/stream/cascaded")
async def cascaded_websocket_endpoint(websocket: WebSocket):
    """
    Dedicated WebSocket endpoint forcing the Phase 12 CascadedPipelineOrchestrator.
    """
    await websocket.accept()
    logger.info("⚡ [VoiceRoute] Dedicated /stream/cascaded connection accepted")
    orchestrator = CascadedPipelineOrchestrator(websocket)
    try:
        await orchestrator.run_loop()
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error in dedicated cascaded orchestrator: {e}")
        await websocket.close()

