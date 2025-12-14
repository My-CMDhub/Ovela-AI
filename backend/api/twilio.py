"""
Twilio Webhooks for Missed Call → WhatsApp Flow
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
from core.config import settings
from services.meta import meta_service
from services.appwrite import db_service
from services.email import email_service
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Default business ID for now (single tenant)
DEFAULT_BUSINESS_ID = "default_business"


@router.post("/incoming-call")
async def handle_incoming_call(
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    CallStatus: str = Form(...)
):
    """
    Handle incoming voice calls from Twilio.
    This returns TwiML to let the call ring and then check status.
    """
    logger.info(f"Incoming call from {From} to {To}, status: {CallStatus}")
    
    # Return TwiML that rings for 20 seconds then hangs up
    # The status callback will handle the missed call
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello, we're currently unavailable. You'll receive a WhatsApp message shortly to help you book an appointment.</Say>
    <Hangup/>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")


@router.post("/call-status")
async def handle_call_status(
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: str = Form(default="0")
):
    """
    Handle call status callbacks from Twilio.
    Triggered when call ends - check if it was missed/no-answer.
    """
    logger.info(f"📞 Call status update: {CallSid} from {From} - Status: {CallStatus}, Duration: {CallDuration}s")
    
    # Normalize phone number (remove + prefix for WhatsApp)
    caller_phone = From.replace("+", "")
    logger.info(f"Normalized phone: {caller_phone}")
    
    # If call was completed but short, or no-answer, send WhatsApp
    if CallStatus in ["completed", "no-answer", "busy", "failed"]:
        try:
            # Get business settings for custom message
            business_settings = db_service.get_all_settings()
            business_name = business_settings.get("business_name", "ibrow threading") if business_settings else "ibrow threading"
            business_phone = business_settings.get("business_phone", "0475 921 152") if business_settings else "0475 921 152"
            
            # Check if this customer has a recently rejected request
            existing_requests = db_service.get_booking_requests_by_phone(caller_phone)
            has_recent_rejection = False
            
            if existing_requests:
                for req in existing_requests:
                    if req.get("status") == "rejected":
                        has_recent_rejection = True
                        break
            
            if has_recent_rejection:
                # Customer calling again after rejection - give contextual message
                message = f"""Hi there! 👋

We noticed you tried calling again. We're sorry we couldn't pick up — {business_name} is quite busy at the moment.

Don't worry! The team has your details and will reach out to you as soon as possible.

If it's urgent, you can try again later at {business_phone}. Thanks for your patience! 💜"""
            else:
                # First-time or regular caller - normal intro
                message = f"""Hi! 👋

Sorry we missed your call at {business_name}.

I'm the virtual assistant here to help you book an appointment. Just let me know:
• Your name
• What service you need
• Your preferred date and time

I'll forward your request to the team and they'll confirm your booking! 💅"""

            await meta_service.send_text_message(caller_phone, message)
            logger.info(f"✅ Sent WhatsApp intro to {caller_phone} (rejection_context: {has_recent_rejection})")
            
            # NOTE: We do NOT create a booking request or send email here.
            # Email is only sent when the customer provides full booking details
            # and the AI submits a booking request via submit_booking_request tool.
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Error handling missed call from {caller_phone}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    else:
        logger.info(f"Call status {CallStatus} - not sending WhatsApp message")
    
    return {"status": "ok"}
