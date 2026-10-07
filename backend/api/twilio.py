"""
Twilio Webhooks for Voice Calls
"""
from fastapi import APIRouter, Request, Form, BackgroundTasks, Depends
from fastapi.responses import Response
from xml.sax.saxutils import escape
from urllib.parse import quote
from core.config import settings
from core.stream_auth import issue_stream_token
from core.twilio_signature import verify_twilio_signature
from services.appwrite import db_service
from services.email import email_service
from datetime import datetime
import logging
import asyncio
from twilio.rest import Client

# Every route here is a Twilio callback (voice, incoming-call, recording-,
# call- and transfer-status, sms), so the signature check sits on the router:
# a route added later cannot forget it. It only rejects in "enforce" mode.
router = APIRouter(dependencies=[Depends(verify_twilio_signature)])
logger = logging.getLogger(__name__)

twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


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
    background_tasks: BackgroundTasks,
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

    
    # Start recording as early as possible for every live call.
    background_tasks.add_task(_enable_recording, CallSid)

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

    # Enforce Abuse Prevention & Rate Limiting — except on the leg returning
    # from a failed staff transfer. That leg is the SAME call (Twilio keeps
    # the CallSid across the <Redirect>) and was admitted already, but its
    # first leg is now counted, so a caller on their 2nd call of the day was
    # told "you have reached our call limit" and hung up on because staff
    # didn't answer. The query flag alone is spoofable, so the exemption is
    # bound to a transcript already existing for this CallSid; without one
    # (e.g. the first leg's save failed) the normal check runs as before.
    returning_from_transfer = (
        transfer_failed == "true"
        and await db_service.call_already_recorded(CallSid, tenant_id)
    )
    if returning_from_transfer:
        logger.info(f"↩️ {CallSid} returning from a failed transfer — rate limit not re-applied")
        is_allowed, limit_reason = True, "transfer_return"
    else:
        is_allowed, limit_reason = await db_service.check_voice_rate_limit(From, tenant_id)
    if not is_allowed:
        logger.warning(f"🚫 Call from {mask_phone(From)} blocked by rate limiting: {limit_reason}")
        # Log blocked attempt as a transcript record with status='blocked'
        await db_service.save_call_transcript(
            tenant_id=tenant_id,
            call_sid=CallSid,
            caller_phone=From,
            transcript=f"[SYSTEM ALERT: Call from {From} blocked by rate limit check. Reason: {limit_reason}]",
            duration=0,
            status="blocked",
            metadata={"reason": limit_reason}
        )
        
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Nicole">Thank you for calling. We are currently experiencing high call volumes, or you have reached our call limit. Please try calling back later or visit our website to complete your reservation. Goodbye!</Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")
        
    # Return TwiML that connects to the AI stream
    # Pass tenant_id to the WebSocket via Parameter
    stream_url = f"wss://{settings.BACKEND_URL.replace('https://', '')}/api/voice/stream"
    # Signed over the raw values below — Twilio unescapes the XML and echoes
    # them back in the stream's `start`, where core/stream_auth verifies them.
    stream_token = issue_stream_token(CallSid, From, tenant_id)

    # Every value is escaped for a double-quoted attribute. From/To/tenant_id
    # and transfer_failed are request input: a From of `"/><Hangup/>` used to
    # rewrite this TwiML. Ordinary values come out byte-identical.
    def attr(value) -> str:
        return escape(str(value), {'"': "&quot;"})

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{attr(stream_url)}">
            <Parameter name="user_phone" value="{attr(From)}" />
            <Parameter name="tenant_id" value="{attr(tenant_id)}" />
            <Parameter name="user_to" value="{attr(To)}" />
            <Parameter name="transfer_failed" value="{attr(transfer_failed)}" />
            <Parameter name="stream_token" value="{attr(stream_token)}" />
        </Stream>
    </Connect>
    <Say voice="Polly.Nicole">I'm sorry, we seem to have lost connection. Please call back. Goodbye!</Say>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")


async def _enable_recording(call_sid: str):
    """Enable recording for active Twilio call.
    
    Single attempt after a brief delay to let the call connect,
    with one fallback path. Runs as a background task so it never
    blocks the TwiML response or event loop.
    """
    recording_status_callback = f"{settings.BACKEND_URL}/twilio/recording-status"

    # Brief delay — gives Twilio time to fully connect the call
    # before we issue the recording API request.
    await asyncio.sleep(0.8)

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: twilio_client.calls(call_sid).recordings.create(
                recording_channels="dual",
                recording_status_callback=recording_status_callback,
                recording_status_callback_method="POST",
            )
        )
        logger.info(f"⏺️ Recording started for call {call_sid}")
        return
    except Exception as e:
        logger.debug(f"Recording create attempt failed for {call_sid}: {e}")

    # Fallback path for accounts/edges that reject recordings.create.
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: twilio_client.calls(call_sid).update(
                record=True,
                recording_channels="dual",
                recording_status_callback=recording_status_callback,
                recording_status_callback_method="POST",
            ),
        )
        logger.info(f"⏺️ Recording enabled via fallback for call {call_sid}")
    except Exception as fallback_error:
        logger.warning(f"Failed to start recording for {call_sid}: {fallback_error}")


@router.post("/recording-status")
async def handle_recording_status(
    RecordingSid: str = Form(...),
    CallSid: str = Form(...),
    RecordingStatus: str = Form(default="unknown"),
    RecordingUrl: str = Form(default=""),
    RecordingDuration: str = Form(default="0"),
):
    """Twilio recording lifecycle callback for verification/debug."""
    logger.info(
        "🎙️ Recording callback: call=%s recording=%s status=%s duration=%ss url=%s",
        CallSid,
        RecordingSid,
        RecordingStatus,
        RecordingDuration,
        RecordingUrl,
    )
    return {"status": "ok"}


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
        
        # Get business phone from Tenant settings. get_tenant_settings is async:
        # un-awaited, `.get` on the coroutine raised and every forwarded call
        # fell through to the "technical difficulties" hangup below.
        business_settings = await db_service.get_tenant_settings(tenant_id)
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

    # A completed call is the only reliable signal that fresh voice spans are
    # on their way to Sentry. Analysis is deferred and fire-and-forget: it must
    # never delay this webhook, which Twilio expects to answer immediately.
    if CallStatus == "completed":
        try:
            from services.latency_watchdog import schedule_post_call_analysis
            schedule_post_call_analysis(CallSid)
        except Exception as e:
            logger.warning(f"🟡 Could not schedule latency analysis: {e}")

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
    request: Request,
    background_tasks: BackgroundTasks,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(default=None),
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
    - "canceled": The dial was cancelled before it connected

    Anything but a connected call returns the caller to the AI AND records a
    staff callback request.
    """
    logger.info(f"📞 Transfer status: {CallSid} - DialCallStatus: {DialCallStatus}")
    
    # "answered" is Twilio's other connected outcome; counting it as a failure
    # would text staff about a call they just took.
    if DialCallStatus in ("completed", "answered"):
        # Transfer succeeded, call ended normally
        logger.info(f"✅ Transfer completed successfully for {mask_phone(From)}")
        return Response(content="<Response><Hangup/></Response>", media_type="application/xml")
    
    # Transfer failed (no-answer / busy / failed / canceled) - return caller to AI
    logger.info(f"⚠️ Transfer failed ({DialCallStatus}) - returning to AI for {mask_phone(From)}")

    # Same tenant resolution as /voice: the orchestrator puts ?tenant_id= on
    # the <Dial> action URL; older calls fall back to the ingress number.
    tenant_id = (
        request.query_params.get("tenant_id")
        or settings.PHONE_TO_TENANT_MAP.get((To or "").replace(" ", "").strip())
        or settings.TENANT_ID
        or "coalcreek"
    )

    # Staff must hear about it: the caller asked for a person and got nobody.
    # A background task runs after this response is sent, so Twilio gets its
    # TwiML immediately; notify_failed_transfer never raises, and scheduling
    # it is guarded too, because nothing here may stop the redirect below.
    try:
        from services.transfer_fallback import notify_failed_transfer
        background_tasks.add_task(
            notify_failed_transfer,
            caller_phone=From,
            tenant_id=tenant_id,
            call_sid=CallSid,
            reason=f"staff line {DialCallStatus or 'unknown'}",
        )
    except Exception as e:
        logger.error(f"🔴 Could not schedule failed-transfer notification: {e}")

    # tenant_id rides along so the returning leg reaches the same tenant even
    # when it was chosen by query param rather than by number. Escaped: it is
    # request input going into XML.
    redirect = "/twilio/voice?transfer_failed=true"
    if request.query_params.get("tenant_id"):
        redirect += f"&tenant_id={quote(tenant_id, safe='')}"
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{escape(redirect)}</Redirect>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")

