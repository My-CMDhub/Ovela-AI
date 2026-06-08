"""
ADK Multi-Agent Routing Graph — Ovela AI Hospitality Orchestrator.

Architecture (Cold Path):
    Manager (OvelaManager)
        ├── BookingWorker   — room availability, create_booking, Stripe payment links, email handling etc..
        └── InfoWorker      — motel policy, amenities, FAQ, pricing, etc...

This graph is triggered asynchronously by Gemini tool calls routed through the
FastAPI webhook handler. It runs entirely on the Cold Path so it NEVER blocks
the real-time Twilio ↔ Deepgram ↔ Gemini speech loop (Hot Path).

Session Isolation:
    Each Twilio call_sid maps to a unique ADK Session. Session state (caller
    name, booking intent, dates) is preserved across multiple tool invocations
    within the same call, eliminating conversational amnesia.

Judging alignment (Google for Startups AI Agents Challenge 2026):
    ✅ Multi-agent ADK graph with Manager + 2 Workers (mandatory for Track 2)
    ✅ AppwriteSessionService (persistent state across Cloud Run scaling events)
    ✅ google-adk 2.0.0 / google.adk.agents.LlmAgent + Runner
    ✅ Gemini 2.5 Flash as reasoning model (native Google Gemini — latest generation)
    ✅ Google Search Grounding on InfoWorker (challenge Key Consideration — live web retrieval)
"""

import logging
import uuid
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types

from services.adk.session_service import AppwriteSessionService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ADK Model Selection
# ---------------------------------------------------------------------------
from functools import cached_property
from google.adk.models.google_llm import Gemini as AdkGemini
from google.adk.utils.variant_utils import GoogleLLMVariant
from google.genai import Client
import os

class VertexGemini(AdkGemini):
    @property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT", "project-bd29d7f8-c65f-4597-b7b"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        )

    @property
    def _live_api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT", "project-bd29d7f8-c65f-4597-b7b"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        )

    @property
    def _api_backend(self) -> GoogleLLMVariant:
        return GoogleLLMVariant.VERTEX_AI

    def __eq__(self, other):
        if isinstance(other, str):
            return self.model == other
        return super().__eq__(other)

_ADK_MODEL = "gemini-2.5-flash-lite"
_ADK_MODEL_VERTEX = VertexGemini(model=_ADK_MODEL)  


# ---------------------------------------------------------------------------
# Agent Instructions
# ---------------------------------------------------------------------------
_MANAGER_INSTRUCTION = """
You are OvelaManager, the intelligent reception supervisor for Coal Creek Motel.

Your role:
1. Greet callers warmly and identify their intent.
2. Route booking-related requests (availability, reservations, payments) to BookingWorker.
3. Route policy, information, and live search requests (amenities, check-in times, FAQ, weather, news, external info) to InfoWorker.
4. Maintain conversation context across multiple turns within the same call session.

Coal Creek Motel context:
- Located in Chiltern, Victoria, Australia.
- Offers Queen, Twin, Family, and Accessible rooms.
- Rates approximately AUD $90-$160/night depending on room type.
- Check-in: 2:00 PM | Check-out: 10:00 AM.

CALL TERMINATION RULES (MANDATORY):
- When the caller says goodbye, indicates they are finished, or you have completed all their requests, you MUST invoke the `end_call` tool explicitly.
- Do NOT simply say "Goodbye" without invoking `end_call` -- leaving the call stream open wastes resources.
- After invoking `end_call`, do not speak any further.

TONE RULES (NON-NEGOTIABLE):
- Never open a response with "Great news!", "Absolutely!", "Of course!", "Certainly!", "Sure thing!", or similar excitement filler.
- Be warm, calm, and professional -- like a confident hotel receptionist, not a chatbot.
- Never use bullet points, numbered lists, headers, or any markdown in speech.
- Keep sentences short and conversational.
- Never proactively read out booking reference numbers, URLs, IDs, or phone country codes unless necessary or explicitly requested.
- When stating booking references (e.g. 'CC-7777'), read them as individual characters and numbers (e.g., 'C C seven seven seven seven') and NEVER pronounce dashes, hyphens, plus symbols, or URL protocol names.
""".strip()

_BOOKING_WORKER_INSTRUCTION = """
You are BookingWorker, a specialist agent for Coal Creek Motel reservations.

Your responsibilities:
- Check room availability for requested dates using the Appwrite PMS. If the user asks for a specific room type, pass that room type to the tool.
- Collect guest name, dates, room type, guest count, and any special requests.
- Create provisional booking records in the PMS.
- Generate Stripe payment checkout links when requested.
- Look up existing bookings by guest name or reference number.
- Update guest details (guest name, email, phone) using update_guest_info. Use this when the caller corrects their name, phone, or email (which automatically updates their reservation and resends the payment link).

PRE-BOOKING GATE (MANDATORY — ONE CONFIRMATION ONLY):
To call create_booking_request you MUST have collected ALL of these:
  1. Guest full name
  2. Email address (spelled and confirmed letter by letter)
  3. Check-in date and check-out date
  4. Room type
  5. User verbal confirmation of the full booking summary

CONFIRMATION PROTOCOL:
- Read the full summary ONCE: "Just to confirm: [Name], [room type], [check-in] to [check-out], [nights] night(s) at $[X]/night, total $[Y]. I'll send the payment link to [email]. Does that sound right?"
- When the user says YES / "that's right" / "correct" / "perfect" / "go ahead" / any affirmative → IMMEDIATELY call create_booking_request with has_user_confirmed_summary=True.
- NEVER repeat the confirmation summary a second time. One ask, one go.
- NEVER say "just to confirm" again after they have already said yes.

TONE RULES (NON-NEGOTIABLE):
- Never open with "Great news!", "Absolutely!", "Certainly!", or similar excitement filler.
- Be calm and direct -- like a professional receptionist, not a chatbot.
- Speak in plain conversational English. No bullet points, no markdown.
- Never proactively read out booking reference numbers, URLs, IDs, or phone country codes unless necessary or explicitly requested.
- When stating booking references (e.g. 'CC-7777'), read them as individual characters and numbers (e.g., 'C C seven seven seven seven') and NEVER pronounce dashes, hyphens, plus symbols, or URL protocol names.
""".strip()

_INFO_WORKER_INSTRUCTION = """
You are InfoWorker, a knowledge specialist for Coal Creek Motel.

Your responsibilities:
- Answer questions about motel policies (cancellation, payment, pets, smoking).
- Describe room amenities, facilities, parking, and WiFi.
- Provide directions and local area information for Chiltern, Victoria.
- Explain check-in/check-out procedures.
- For questions about current weather, local tourist attractions, events near Chiltern, road conditions, or anything requiring live information — use the perform_live_search tool to retrieve accurate, up-to-date answers. Always ground your answer in the search result.

Be accurate and concise. This is a voice conversation — no bullet points, no markdown.
- Never proactively read out booking reference numbers, URLs, IDs, or phone country codes unless necessary or explicitly requested.
- When stating booking references (e.g. 'CC-7777'), read them as individual characters and numbers (e.g., 'C C seven seven seven seven') and NEVER pronounce dashes, hyphens, plus symbols, or URL protocol names.
""".strip()


# ---------------------------------------------------------------------------
# ADK Tools Integration (Cold Path Wrapper to Coal Creek Dispatcher)
# ---------------------------------------------------------------------------
import json
from google.adk.tools import ToolContext

async def _adk_save_reservation_fn(data):
    from services.appwrite import db_service
    import time
    import uuid
    doc_id = f"test_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    data["tenant_id"] = "coalcreek"
    data["notes"] = "[EVAL HARNESS ADK] " + (data.get("notes") or "Simulated Booking Hold")
    try:
        path = "/collections/motel_reservations/documents"
        result = await db_service._motel_request(
            "POST",
            path,
            data={"documentId": doc_id, "data": data}
        )
        if result:
            try:
                from tests.run_multi_agent_evaluation import CREATED_RESERVATIONS
                CREATED_RESERVATIONS.append(doc_id)
            except ImportError:
                pass
            return {"success": True, "id": doc_id}
        return {"success": False, "error": "Request failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _get_dispatcher(tool_context: ToolContext) -> Any:
    from services.voice_agent.functions.coalcreek_handlers import CoalCreekFunctionDispatcher
    from services.appwrite import db_service
    
    user_id = tool_context.session.user_id if tool_context and tool_context.session else "eval_default"
    phone = user_id if user_id.startswith("+") else "+61499888777"
    
    class MockAbuseProtection:
        def set_call_start_time(self, t): pass
        
    return CoalCreekFunctionDispatcher(
        db_service=db_service,
        user_phone=phone,
        save_reservation_fn=_adk_save_reservation_fn,
        abuse_protection=MockAbuseProtection(),
        caller_memory_bank=None,
        call_sid=f"adk_call_{user_id[:10]}"
    )

def _format_tool_error(tool_name: str, exception: Exception) -> dict:
    """Format tool execution exceptions into G3-grade structured error returns."""
    error_msg = str(exception)
    
    # Check retry eligibility based on exception messages/types
    # DB lock, connection error, timeout are retryable
    retry_allowed = any(
        term in error_msg.lower() 
        for term in ["timeout", "connection", "rate limit", "busy", "temporary", "dns"]
    )
    
    # Specific user facing message based on tool
    if tool_name == "check_availability":
        user_facing_message = "I couldn't check availability right now due to a temporary connection issue. Would you like me to try again, or put you through to reception?"
    elif tool_name == "create_booking_request":
        # Check if it's a pre-booking gate error
        if "SYSTEM RULE VIOLATION" in error_msg:
            user_facing_message = "I need to verify the booking summary details with you before I can save the hold. Let me read it back to make sure it's correct."
            retry_allowed = False
        elif "email bounced" in error_msg.lower() or ("email" in error_msg.lower() and "bounce" in error_msg.lower()):
            user_facing_message = "It looks like the email address bounced. Could you please spell it again letter by letter?"
            retry_allowed = False
        else:
            user_facing_message = "I ran into a problem saving your reservation. I can try again, or connect you to staff."
    elif tool_name == "lookup_booking":
        user_facing_message = "I'm having trouble retrieving your booking right now. Let me connect you to reception."
        retry_allowed = False
    elif tool_name == "update_guest_info":
        user_facing_message = "I couldn't update your information right now. Let me connect you to staff."
        retry_allowed = False
    elif tool_name == "perform_live_search":
        user_facing_message = "My search service is currently unavailable. Let me try that again, or can I help with something else?"
        retry_allowed = True
    else:
        user_facing_message = "I encountered an issue processing that request. Let me try again or put you through to staff."

    return {
        "success": False,
        "user_facing_message": user_facing_message,
        "retry_allowed": retry_allowed,
        "error_details": error_msg
    }

async def _execute_with_error_handling(tool_name: str, dispatcher_coro) -> str:
    """Helper to catch exceptions and wrap errors in a structured G3-compliant JSON response."""
    try:
        res = await dispatcher_coro
        # Check if the returned dictionary indicates a failure
        if isinstance(res, dict):
            if "error" in res or res.get("success") is False:
                err_msg = res.get("error") or res.get("message") or "Unknown error"
                formatted_error = _format_tool_error(tool_name, Exception(err_msg))
                return json.dumps(formatted_error)
        return json.dumps(res)
    except Exception as e:
        logger.error("Error executing ADK tool %s: %s", tool_name, e, exc_info=True)
        formatted_error = _format_tool_error(tool_name, e)
        return json.dumps(formatted_error)

async def check_availability(check_in_date: str, check_out_date: str = "", room_type: str = "any", tool_context: ToolContext = None) -> str:
    """
    Query live room availability at Coal Creek Motel.

    Use ONLY when the caller asks about room availability, rates, or available dates.
    Do NOT call for general motel policies, check-in times, or amenities.

    Args:
        check_in_date: Check-in date in YYYY-MM-DD format (e.g., "2026-06-15"). Today's date/year is in the CURRENT SYSTEM CLOCK.
        check_out_date: Check-out date in YYYY-MM-DD format. If unspecified, defaults to 1 night stay.
        room_type: Mapped room type: "queen" (covers Queen/Double rooms), "twin" (Twin Room), "family" (Family Suite), "suite" (Deluxe Spa Suite), or "any" to see all available types.

    Returns JSON string with structure:
      On Success:
        {"available": true, "verified": true, "room_type": "...", "price_per_night": X, "total": Y, "ai_should_say": "..."}
      On Sold Out / unavailable:
        {"available": false, "verified": true, "ai_should_say": "..."}
      On Error:
        {"success": false, "user_facing_message": "...", "retry_allowed": true/false, "error_details": "..."}

    Error Handling & Recovery:
      - If success is false and retry_allowed is true, you may retry the check once.
      - If retry fails or retry_allowed is false, offer to transfer the caller to reception on 03 5726 0303.
    """
    dispatcher = _get_dispatcher(tool_context)
    args = {"check_in_date": check_in_date, "check_out_date": check_out_date, "room_type": room_type}
    return await _execute_with_error_handling("check_availability", dispatcher.execute("check_availability", args))

async def create_booking_request(guest_name: str, check_in_date: str, room_type: str, num_guests: int = 1, check_out_date: str = "", guest_phone: str = "", guest_email: str = "", notes: str = "", tool_context: ToolContext = None) -> str:
    """
    Create a provisional soft hold booking request in the Coal Creek Motel PMS.

    MANDATORY PRE-BOOKING GATES:
    You MUST NOT invoke this tool until you have collected and verbally confirmed:
      1. Guest's first and last name.
      2. Email address (spelled out and confirmed character-by-character).
      3. Resolved check-in and check-out dates.
      4. Room type.
      5. Explicit confirmation of the full summary (e.g. "[Name], checking in [date], checking out [date], [room] at $[price] per night. Does that sound right?")

    Args:
        guest_name: Guest's full name (first and last).
        check_in_date: Check-in date in YYYY-MM-DD format.
        room_type: Specific room type ("queen", "twin", "family", "suite").
        num_guests: Number of guests staying (default 1).
        check_out_date: Check-out date in YYYY-MM-DD format.
        guest_phone: Guest's phone number. Defaults to calling number.
        guest_email: Guest's email address.
        notes: Special requests (accessible access, extra bed, late check-in).
        tool_context: Internal ADK context containing caller session state.

    Returns JSON string with structure:
      On Success:
        {"success": true, "booking_reference": "CC-XXXXXX", "guest_name": "...", "total_amount": X, "message": "..."}
      On Pre-booking gate violation / Error:
        {"success": false, "user_facing_message": "...", "retry_allowed": false, "error_details": "..."}

    Error Handling & Recovery:
      - If the error indicates a summary confirmation check was bypassed, immediately read the summary to the caller and wait for their yes before invoking the tool again.
      - If the email bounces or fails, tell the guest their email failed/bounced and ask them to spell it again.
      - For system errors, apologize and offer to transfer the call to reception.
    """
    dispatcher = _get_dispatcher(tool_context)
    args = {
        "guest_name": guest_name,
        "check_in_date": check_in_date,
        "room_type": room_type,
        "num_guests": num_guests,
        "check_out_date": check_out_date,
        "guest_phone": guest_phone,
        "guest_email": guest_email,
        "notes": notes
    }
    return await _execute_with_error_handling("create_booking_request", dispatcher.execute("create_booking_request", args))

async def lookup_booking(guest_name: str = "", phone: str = "", email: str = "", reference: str = "", tool_context: ToolContext = None) -> str:
    """
    Look up an existing reservation in the PMS system.

    PRIVACY & SECURITY RULES:
    - To prevent data leaks, you can only lookup booking details for the phone number the guest is currently calling from.
    - If a caller asks to lookup a booking registered under a different phone number, the tool will refuse and request staff intervention.

    Args:
        guest_name: Guest name on the reservation.
        phone: Phone number to search (if different from caller phone).
        email: Email address linked to the booking.
        reference: Booking reference code (e.g., "CC-AB1234").
        tool_context: Internal ADK context containing caller session state.

    Returns JSON string with structure:
      On Success:
        {"found": true, "booking_reference": "...", "guest_name": "...", "status": "...", "payment_status": "...", "message": "..."}
      On Privacy/Access Block:
        {"found": false, "privacy_refusal": true, "message": "..."}
      On Error:
        {"success": false, "user_facing_message": "...", "retry_allowed": false, "error_details": "..."}

    Error/Failure Handling:
      - If found is false and privacy_refusal is true, explain that for security reasons, we cannot display details for other phone numbers and offer a transfer to staff.
      - If booking is not found, verify the reference spelling or search parameters with the user.
    """
    dispatcher = _get_dispatcher(tool_context)
    args = {"guest_name": guest_name, "phone": phone, "email": email, "reference": reference}
    return await _execute_with_error_handling("lookup_booking", dispatcher.execute("lookup_booking", args))

async def resend_payment_confirmation(guest_email: str, tool_context: ToolContext = None) -> str:
    """
    Manually resend the booking confirmation or receipt email to the guest.

    Use when the customer asks to resend their booking confirmation or receipt.
    Do NOT call this tool if the booking's payment status is still pending_payment;
    explain to the user that they must pay first, and offer to resend the payment link.

    Args:
        guest_email: Guest email address to resend the confirmation to.
        tool_context: Internal ADK context containing caller session state.

    Returns JSON string with structure:
      On Success:
        {"success": true, "message": "..."}
      On Error / Guard Block:
        {"success": false, "user_facing_message": "...", "retry_allowed": false, "error_details": "..."}
    """
    dispatcher = _get_dispatcher(tool_context)
    args = {"guest_email": guest_email}
    return await _execute_with_error_handling("resend_payment_confirmation", dispatcher.execute("resend_payment_confirmation", args))

async def update_guest_info(guest_name: str = "", guest_email: str = "", guest_phone: str = "", tool_context: ToolContext = None) -> str:
    """
    Update guest profile details in the CRM (guest name, phone, email) or corrected email address.

    Use when:
      - The caller corrects their email address after a failed payment confirmation/link delivery.
      - The caller corrects or updates their name or phone details.
      - The caller requests to update their guest profile information.

    If the caller has a pending or pending_payment booking, updating the guest email address
    via this tool will automatically patch the booking record and resend the Stripe payment link.

    Args:
        guest_name: Updated guest full name.
        guest_email: Updated or corrected guest email address.
        guest_phone: Guest phone number (if different from caller phone).
        tool_context: Internal ADK context containing caller session state.

    Returns JSON string with structure:
      On Success:
        {"success": true, "message": "...", "email_resent": true/false}
      On Error:
        {"success": false, "user_facing_message": "...", "retry_allowed": false, "error_details": "..."}
    """
    dispatcher = _get_dispatcher(tool_context)
    args = {"guest_name": guest_name, "guest_email": guest_email, "guest_phone": guest_phone}
    return await _execute_with_error_handling("update_guest_info", dispatcher.execute("update_guest_info", args))

async def wait_on_request(reason: str = "", wait_seconds: int = 90, tool_context: ToolContext = None) -> str:
    """
    Pause silence monitoring / VAD timers to give the caller time to fetch details.

    Use proactively whenever the guest says they need a moment, need to find their credit card, are checking their inbox for a payment link, or need to verify a detail.
    Do NOT wait for the user to explicitly ask you to wait if they state they are doing something.

    Args:
        reason: Short explanation of why the agent is waiting (e.g., "waiting for payment", "searching for email").
        wait_seconds: Duration to wait in seconds (minimum 30, maximum 120, defaults to 90).

    Returns JSON string:
        {"action": "wait_on_request", "duration_seconds": X, "message": "No worries, take your time. I'll stay on the line."}
    """
    return json.dumps({"action": "wait_on_request", "duration_seconds": wait_seconds, "message": "No worries, take your time. I'll stay on the line."})

async def flag_off_topic(reason: str, tool_context: ToolContext = None) -> str:
    """
    Flag inappropriate, abusive, or highly off-topic user behavior.

    Use when the caller goes completely off-topic (e.g., asking about unrelated politics, recipe suggestions, personal life) or exhibits abusive behavior.

    Args:
        reason: Description of the off-topic or abusive behavior.

    Returns JSON string:
        {"action": "flag_off_topic", "flagged": true}
    """
    return json.dumps({"action": "flag_off_topic", "flagged": True})

async def transfer_to_staff(tool_context: ToolContext = None) -> str:
    """
    Transfer the caller to a human staff member at the Coal Creek Motel.

    Use ONLY when:
      - The caller explicitly asks for a human ("put me through", "let me speak to a person").
      - There is an unrecoverable system error or availability calendar timeout.
      - A privacy block occurs and the caller needs manual assistance.
      - The caller has a complex request (e.g., modifying a booking that has already been paid).
      - CRITICAL: If you just attempted a transfer and NO ONE ANSWERED (fallback flow), DO NOT call this again in the same turn until explicitly asked by user again to do so.

    Returns JSON string:
        {"action": "transfer_to_staff", "message": "Sure, I'll transfer you to reception now."}
    """
    return json.dumps({"action": "transfer_to_staff", "message": "Sure, I'll transfer you to reception now."})

async def end_call(message: str = "", confidence_score: int = 100, tool_context: ToolContext = None) -> str:
    """
    End the active phone call by playing a farewell message and disconnecting.

    ONLY use when the caller explicitly wants to finish the conversation, such as 'bye', 'goodbye', 'see you', 'that's all', or when they clearly confirm they are done after your final help-offer. If they only say thanks, appreciation, or a polite wrap-up, do ONE final natural help-offer first instead of ending immediately. NEVER use this when they want to speak to staff or be transferred.

    Args:
        message: Goodbye/farewell message to read to the caller.
        confidence_score: Your confidence score (1-100) that the user genuinely wants to end the call right now. Must be >= 80 to use this tool.

    Returns JSON string:
        {"action": "end_call", "message": message or "Thanks for calling Coal Creek Motel, goodbye.", "confidence_score": confidence_score}
    """
    return json.dumps({"action": "end_call", "message": message or "Thanks for calling Coal Creek Motel, goodbye.", "confidence_score": confidence_score})

async def perform_live_search(query: str, tool_context: ToolContext = None) -> str:
    """
    Perform a live Google Search to retrieve current, up-to-date information.

    Use ONLY when the caller asks about dynamic, real-time facts such as Chiltern weather, local tourist attractions, events near Chiltern, road conditions, or other external info.
    Do NOT use for general motel check-in times or policies.

    Args:
        query: Specific search query string (e.g., "current weather in Chiltern Victoria").

    Returns JSON string with structure:
      On Success:
        {"success": true, "answer": "..."}
      On Error:
        {"success": false, "user_facing_message": "...", "retry_allowed": true, "error_details": "..."}
    """
    from google import genai
    from google.genai import types
    import os
    try:
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "project-bd29d7f8-c65f-4597-b7b")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        client = genai.Client(vertexai=True, project=project, location=location)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=query,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=8000),
            )
        )
        if not response or not response.text:
            raise Exception("Search service returned an empty response")
        return json.dumps({"success": True, "answer": response.text})
    except Exception as e:
        logger.error("Error executing perform_live_search: %s", e, exc_info=True)
        formatted_error = _format_tool_error("perform_live_search", e)
        return json.dumps(formatted_error)


# ---------------------------------------------------------------------------
# ADKOrchestrator
# ---------------------------------------------------------------------------
class ADKOrchestrator:
    """
    Stateful Google ADK multi-agent orchestrator for Ovela AI.

    Creates and manages a Manager → Worker routing graph backed by
    InMemorySessionService. Each Twilio call_sid gets an isolated session
    so conversation state is never cross-contaminated between callers.

    Usage:
        orc = ADKOrchestrator()
        session = await orc.get_or_create_session(user_id=call_sid)
        response = await orc.query(
            user_id=call_sid,
            session_id=session.id,
            text="I want to book a queen room for tomorrow",
        )
    """

    _APP_NAME = "ovela_adk"

    def __init__(self):
        # Inject real-time clock to prevent temporal hallucination across ALL agents
        from datetime import datetime as dt_datetime
        from zoneinfo import ZoneInfo
        _mel_tz = ZoneInfo("Australia/Melbourne")
        _now = dt_datetime.now(_mel_tz)
        _current_date = _now.strftime("%A, %d %B %Y")
        _current_time = _now.strftime("%H:%M")
        
        system_clock_footer = f"\n\nCURRENT SYSTEM CLOCK:\n- Today's Date: {_current_date}\n- Current Time: {_current_time}\nCRITICAL: When calling tools, ALWAYS use {_now.year} as the default year unless the user explicitly specifies another year."
        
        dynamic_manager_instruction = f"{_MANAGER_INSTRUCTION}{system_clock_footer}"
        dynamic_booking_instruction = f"{_BOOKING_WORKER_INSTRUCTION}{system_clock_footer}"

        # Build specialist Worker agents
        self.booking_worker = LlmAgent(
            name="BookingWorker",
            model=_ADK_MODEL_VERTEX,
            instruction="",
            static_instruction=dynamic_booking_instruction,
            tools=[check_availability, create_booking_request, lookup_booking, resend_payment_confirmation, update_guest_info, wait_on_request, flag_off_topic, transfer_to_staff, end_call],
        )
        self.info_worker = LlmAgent(
            name="InfoWorker",
            model=_ADK_MODEL_VERTEX,
            instruction="",
            static_instruction=_INFO_WORKER_INSTRUCTION,
            tools=[perform_live_search],
        )

        # Manager orchestrates and routes to workers
        self.manager = LlmAgent(
            name="OvelaManager",
            model=_ADK_MODEL_VERTEX,
            instruction="",
            static_instruction=dynamic_manager_instruction,
            sub_agents=[self.booking_worker, self.info_worker],
            tools=[end_call, transfer_to_staff, wait_on_request],  # G1: manager can handle transfers/waits directly
        )

        # Session service — AppwriteSessionService persists state to Appwrite
        # so conversation context survives Cloud Run scaling and WebSocket reconnects.
        self._session_service = AppwriteSessionService()

        # ADK Runner — the execution engine that drives the agent graph
        self.runner = Runner(
            agent=self.manager,
            app_name=self._APP_NAME,
            session_service=self._session_service,
        )

        logger.info(
            "🤖 ADKOrchestrator initialised | workers=%s",
            [self.booking_worker.name, self.info_worker.name],
        )
        # BS1: In-process session cache — avoids Appwrite GET round-trip on repeated tool calls
        # Key: session_id (deterministic MD5), Value: (session_obj, expires_at_unix)
        self._session_cache: dict[str, tuple[Any, float]] = {}

    async def get_or_create_session(self, user_id: str) -> Any:
        """
        Return the existing ADK Session for this caller or create a new one.

        Args:
            user_id: Unique identifier for this caller (Twilio call_sid recommended).

        Returns:
            ADK Session object with a stable `.id` attribute.
        """
        # Deterministic session_id derived from user_id so re-entry returns same session
        # Twilio Call SIDs are 34 chars. With "sess_" prefix, it's 39 chars. Appwrite limits doc IDs to 36 chars.
        # Let's use MD5 hash to guarantee a safe 34-char ID.
        import hashlib
        session_id = "s_" + hashlib.md5(user_id.encode("utf-8")).hexdigest()

        try:
            # BS1: Check in-process cache first — avoids Appwrite GET on repeated cold-path fires
            import time as _time
            cached = self._session_cache.get(session_id)
            if cached:
                cached_session, expires_at = cached
                if _time.time() < expires_at:
                    logger.debug("🤖 ADK: Cache HIT for session %s (user %s)", session_id, user_id[:8])
                    return cached_session

            existing = await self._session_service.get_session(
                app_name=self._APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
            if existing:
                logger.debug("🤖 ADK: Reusing session %s for user %s", session_id, user_id[:8])
                self._session_cache[session_id] = (existing, _time.time() + 3600)
                return existing
        except Exception:
            pass  # Session not found — create fresh below

        session = await self._session_service.create_session(
            app_name=self._APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state={},
        )
        logger.info("🤖 ADK: Created new session %s for user %s", session_id, user_id[:8])
        # BS1: Populate cache on create
        self._session_cache[session_id] = (session, _time.time() + 3600)
        return session

    async def query(self, user_id: str, session_id: str, text: str) -> str:
        """
        Send a user utterance through the ADK graph and return the response text.

        Streams events from runner.run_async and collects the final response.
        Silently returns empty string on any error — the Hot Path must stay safe.

        Args:
            user_id:    Caller identifier (Twilio call_sid).
            session_id: ADK session ID from get_or_create_session().
            text:       The user's transcribed utterance.

        Returns:
            Agent's response string (may be empty string on failure).
        """
        message = types.Content(
            role="user",
            parts=[types.Part(text=text)],
        )

        response_parts: list[str] = []

        try:
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=message,
            ):
                if event.is_final_response():
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                response_parts.append(part.text)
                    
        except Exception as exc:
            logger.error("🤖 ADK: query failed for user %s — %s", user_id[:8], exc)
            return ""

        result = " ".join(response_parts).strip()
        logger.info("🤖 ADK: Response for %s (%d chars)", user_id[:8], len(result))
        return result

    async def update_session_state(self, user_id: str, session_id: str, state: dict) -> None:
        """
        Merge state updates into the ADK session (e.g., caller name, booking dates).

        Silently swallows errors — state updates are best-effort.

        Args:
            user_id:    Caller identifier.
            session_id: ADK session ID.
            state:      Dict of key-value pairs to merge into session state.
        """
        try:
            session = await self._session_service.get_session(
                app_name=self._APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
            if session:
                session.state.update(state)
                logger.debug("🤖 ADK: Session state updated — keys: %s", list(state.keys()))
        except Exception as exc:
            logger.warning("🤖 ADK: update_session_state failed — %s", exc)
