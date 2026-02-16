"""
Twilio Webhooks for Voice Calls
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
from core.config import settings
from services.appwrite import db_service
from services.email import email_service
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


# Default business ID for now (single tenant)
DEFAULT_BUSINESS_ID = "default_business"

def mask_phone(phone: str) -> str:
    """Mask phone number for logging (e.g. +614...123)."""
    if not phone or len(phone) < 8:
        return "..."
    return f"{phone[:4]}...{phone[-3:]}"


@router.post("/voice")
async def handle_voice_webhook(
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(default=None),
    tenant_id: str = None  # Allow passing via Query Param (e.g. /voice?tenant_id=coalcreek)
):
    """
    Main voice webhook - connects caller to AI agent.
    
    Multi-Tenant Strategy:
    1. Query Param: Configure Twilio Webhook as https://api.../voice?tenant_id=coalcreek
    2. 'To' Number Lookup: Fallback to mapping known numbers
    3. Default: Env var or 'coalcreek'
    """
    logger.info(f"📞 Voice webhook from {mask_phone(From)} to {mask_phone(To)} (tenant_id={tenant_id}), CallSid: {CallSid}")

    
    # Resolve tenant_id
    # 1. Check Query Param explicitly from request (override)
    tenant_id = request.query_params.get("tenant_id")
    transfer_failed = request.query_params.get("transfer_failed", "false")
    
    if not tenant_id:
        # 2. Check Phone Mapping (Ingress Number)
        cleaned_to = To.replace(" ", "").strip() if To else ""
        if cleaned_to in settings.PHONE_TO_TENANT_MAP:
            tenant_id = settings.PHONE_TO_TENANT_MAP[cleaned_to]
            logger.info(f"📍 Mapped Ingress Number {cleaned_to} -> {tenant_id}")
        else:
            # 3. Default Fallback
            tenant_id = settings.TENANT_ID or "coalcreek"
            logger.info(f"⚠️ Unknown Ingress Number {cleaned_to} -> Fallback to {tenant_id}")
        
    # Return TwiML that connects to the AI stream
    # Pass tenant_id to the WebSocket via Parameter
    stream_url = f"wss://{settings.BACKEND_URL.replace('https://', '')}/api/voice/stream"
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="user_phone" value="{From}" />
            <Parameter name="tenant_id" value="{tenant_id}" />
            <Parameter name="user_to" value="{To}" />
            <Parameter name="transfer_failed" value="{transfer_failed}" />
        </Stream>
    </Connect>
    <Say voice="Polly.Nicole">I'm sorry, we seem to have lost connection. Please call back. Goodbye!</Say>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")


@router.post("/incoming-call")
async def handle_incoming_call(
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    CallStatus: str = Form(...)
):
    """
    Handle incoming voice calls from Twilio.
    Forwards the call to the business owner's phone.
    """
    logger.info(f"📞 Incoming call from {mask_phone(From)} to {mask_phone(To)}, CallSid: {CallSid}")
    
    try:
        # Resolve tenant from To number
        tenant_id = settings.PHONE_TO_TENANT_MAP.get(To.replace(" ", "").strip()) or settings.TENANT_ID or "coalcreek"
        
        # Get business phone from Tenant settings
        business_settings = db_service.get_tenant_settings(tenant_id)
        business_phone = business_settings.get("business_phone") if business_settings else None
        
        if not business_phone:
            logger.error(f"❌ Business phone not configured for tenant {tenant_id}")
            # Fallback: Play error message
            twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Sorry, the business phone is not configured.</Say>
    <Hangup/>
</Response>"""
            return Response(content=twiml, media_type="application/xml")
        
        # Ensure phone number has + prefix for international format
        if not business_phone.startswith("+"):
            business_phone = f"+{business_phone}"
        
        logger.info(f"🔄 Forwarding call to business phone: {mask_phone(business_phone)}")
        
        # Return TwiML that forwards the call to business phone
        # timeout: Ring for 30 seconds before giving up
        # action: Callback URL to handle the result of the dial attempt
        callback_url = f"{settings.BACKEND_URL}/twilio/call-status"
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial timeout="10" action="{callback_url}" method="POST">
        <Number>{business_phone}</Number>
    </Dial>
    <Say voice="alice">Sorry, we couldn't connect your call. Please try again later.</Say>
</Response>"""
        
        return Response(content=twiml, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"❌ Error in incoming call handler: {e}")
        # Fallback to safe error message
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Sorry, we're experiencing technical difficulties. Please try again later.</Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")


@router.post("/call-status")
async def handle_call_status(
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: str = Form(default="0"),
    # Dial-specific parameters (only present when using <Dial> verb)
    DialCallStatus: str = Form(default=None),
    DialCallDuration: str = Form(default="0")
):
    """
    Handle call status callbacks from Twilio.
    Triggered after the <Dial> attempt completes.
    Using for logging purposes.
    """
    logger.info(f"📞 Call status callback: {CallSid} from {mask_phone(From)}")
    logger.info(f"   CallStatus: {CallStatus}, CallDuration: {CallDuration}s")
    logger.info(f"   DialCallStatus: {DialCallStatus}, DialCallDuration: {DialCallDuration}s")
    
    return {"status": "ok"}


@router.post("/sms")
async def handle_incoming_sms(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    To: str = Form(...),
    tenant_id: str = None
):
    """
    Handle incoming SMS messages.
    """
    # Resolve tenant_id from query params
    tenant_id = request.query_params.get("tenant_id")
    
    logger.info(f"📩 Incoming SMS from {mask_phone(From)} to {mask_phone(To)} (tenant_id={tenant_id}): '{Body}'")
    
    return Response(content="", media_type="text/plain")


@router.post("/transfer-status")
async def handle_transfer_status(
    CallSid: str = Form(...),
    From: str = Form(...),
    DialCallStatus: str = Form(default=None),
    DialCallDuration: str = Form(default="0")
):
    """
    Handle transfer result callback.
    
    DialCallStatus values:
    - "completed": Staff answered and conversation ended
    - "no-answer": Staff didn't answer within timeout
    - "busy": Staff line was busy
    - "failed": Call failed to connect
    """
    logger.info(f"📞 Transfer status: {CallSid} - DialCallStatus: {DialCallStatus}")
    
    if DialCallStatus == "completed":
        # Transfer succeeded, call ended normally
        logger.info(f"✅ Transfer completed successfully for {mask_phone(From)}")
        return Response(content="<Response><Hangup/></Response>", media_type="application/xml")
    
    # Transfer failed - return caller to AI
    logger.info(f"⚠️ Transfer failed ({DialCallStatus}) - returning to AI for {mask_phone(From)}")
    
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">/twilio/voice?transfer_failed=true</Redirect>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")

