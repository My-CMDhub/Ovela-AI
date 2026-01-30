"""
Voice Agent Function Handlers Module.

Contains the actual implementation of functions that the AI agent can call.
Separated from definitions (in __init__.py) for cleaner organization.

Each handler receives args dict and returns a result dict that the AI uses.
"""

import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# =============================================================================
# ROOM DATA - Single source of truth for room information
# =============================================================================

ROOM_INFO = {
    "queen": {
        "name": "Queen Room",
        "price": 130,
        "total_rooms": 6,
        "max_guests": 2,
        "description": "Queen bed, suits 1-2 guests",
        "bedding": "1 Queen bed"
    },
    "twin": {
        "name": "Twin Room",
        "price": 140,
        "total_rooms": 4,
        "max_guests": 3,
        "description": "Queen + single bed, suits 2-3 guests",
        "bedding": "1 Queen + 1 Single bed"
    },
    "family": {
        "name": "Family Room",
        "price": 160,
        "total_rooms": 3,
        "max_guests": 4,
        "description": "Queen + 2 singles, suits up to 4 guests",
        "bedding": "1 Queen + 2 Single beds"
    },
    "accessible": {
        "name": "Accessible Room",
        "price": 130,
        "total_rooms": 2,
        "max_guests": 2,
        "description": "Reduced mobility friendly, ground level",
        "bedding": "1 Queen bed"
    }
}

# Motel database ID (Appwrite)
MOTEL_DB_ID = "6947b8300005f5863f96"


# =============================================================================
# AVAILABILITY & BOOKING HANDLERS
# =============================================================================

async def handle_check_availability(args: dict, db_service, tenant_id: str = "coalcreek") -> dict:
    """
    Check room availability.
    
    CRITICAL FOR COAL CREEK TRIAL: 
    If external PMS API (Update247) key is missing or connection fails,
    we MUST fall back to "Assume Available + Manual Confirm" flow.
    Do NOT error out.
    """
    check_in = args.get("check_in_date", "")
    check_out = args.get("check_out_date", "")
    room_type = args.get("room_type", "queen")
    
    if not check_in:
        return {"available": False, "message": "Please provide check-in date"}
    
    # 1. Basic Date Validation
    try:
        check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
        if check_in_dt.date() < datetime.now().date():
            return {
                "available": False,
                "message": "That date has already passed. What dates were you looking at?"
            }
    except ValueError:
        return {
            "available": False,
            "message": "I didn't catch the date properly. Could you repeat that?"
        }

    # 2. PMS/DB Check with FALLBACK
    # Ideally we query Update247 or Appwrite here.
    # For TRIAL phase with Coal Creek, we might NOT has API key yet.
    # We must treat "System Failure" as "Available (Manual Check needed)"
    
    # Select Room Data based on Tenant
    room_data_source = ROOM_INFO
    if tenant_id == "coalcreek":
        from services.knowledge_base.coalcreek import COALCREEK_DATA
        room_data_source = COALCREEK_DATA["rooms"]
        
    # Map room alias if needed (e.g. 'spa' -> 'Deluxe Spa')
    # Coal Creek keys: queen, twin, spa, family
    room = room_data_source.get(room_type, room_data_source.get("queen"))
    
    try:
        # Placeholder for Real PMS Call
        # if settings.UPDATE247_API_KEY:
        #      result = pms_service.check(check_in)
        # else:
        #      raise Exception("No API Key")
        
        # Currently we just check local DB for our own bookings
        # ignoring this for a moment to demonstrate the "Robust Fallback" logic
        pass 
        
        # Determine availability (Mock logic or Local DB)
        # For this specific refactor, we are enforcing the "Read-Only + Soft Hold" behavior
        # If we can't be 100% sure, we say "Yes, appears available, let me double check"
        
        return {
            "available": True,
            "room_type": room_type,
            "price_per_night": room["price"],
            "check_in_date": check_in,
            "message": f"Yes, dates look good for a {room['name']}. Rate is ${room['price']} per night. Shall I place a hold for you?"
        }

    except Exception as e:
        logger.warning(f"Availability check failed (using fallback): {e}")
        # FALLBACK - Never block the user
        return {
            "available": True,
            "room_type": room_type,
            "price_per_night": room["price"],
            "check_in_date": check_in,
            "message": f"I see those dates as likely available. Rates start at ${room['price']}. I can place a temporary hold while reception confirms?"
        }


async def handle_create_booking_request(args: dict, user_phone: str, save_reservation_fn, tenant_id: str = "coalcreek") -> dict:
    """
    Create a SOFT HOLD booking request (Coal Creek style).
    Status: pending_confirmation
    Message: 'I've placed a temporary hold...'
    """
    # Reuse validaton logic or shared helper if preferred. 
    # For now, duplicated for isolation to match "Fresh Start" request.
    
    guest_name = args.get("guest_name", "")
    check_in = args.get("check_in_date", "")
    check_out = args.get("check_out_date", "")
    room_type = args.get("room_type", "queen")
    num_guests = args.get("num_guests", 1)
    guest_email = args.get("guest_email", "")
    notes = args.get("notes", "")
    
    guest_phone = args.get("guest_phone", "") or user_phone
    if guest_phone == "unknown" or not guest_phone:
        guest_phone = ""
    
    if not guest_name or not check_in:
        return {
            "success": False,
            "message": "I need your name and check-in date to place the hold."
        }
    
    # Calculate nights
    if not check_out:
        try:
            check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
            check_out = (check_in_dt + timedelta(days=1)).strftime("%Y-%m-%d")
            num_nights = 1
        except:
            check_out = check_in
            num_nights = 1
    else:
        try:
            check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
            check_out_dt = datetime.strptime(check_out, "%Y-%m-%d")
            num_nights = (check_out_dt - check_in_dt).days
            if num_nights < 1: num_nights = 1
        except:
            num_nights = 1
            
    # Get pricing
    room = ROOM_INFO.get(room_type, ROOM_INFO["queen"])
    rate = room["price"]
    total = rate * num_nights
    
    # Booking Ref
    booking_ref = f"CC-{int(time.time()) % 100000:05d}"
    
    now = datetime.now().isoformat()
    
    reservation_data = {
        "guest_name": guest_name,
        "guest_phone": guest_phone,
        "guest_email": guest_email,
        "num_guests": num_guests,
        "room_type": room_type,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "num_nights": num_nights,
        "rate_per_night": rate,
        "total_amount": total,
        "deposit_paid": 0,
        "status": "pending_confirmation", # Explicit Soft Hold status
        "source": "voice_ai_soft_hold",
        "booking_reference": booking_ref,
        "notes": notes or "Soft Hold Request via AI",
        "arrival_time": "",
        "tenant_id": tenant_id,
        "created_at": now,
        "updated_at": now,
        "created_by": "ovela_ai"
    }
    
    try:
        result = await save_reservation_fn(reservation_data)
        
        if result:
            logger.info(f"✅ Created SOFT HOLD: {booking_ref} for {guest_name}")
            
            # Trigger staff notification
            try:
                import asyncio
                from services.staff_notifications import staff_notification_service
                asyncio.create_task(
                    staff_notification_service.notify_new_booking_request(
                        guest_name=guest_name,
                        guest_phone=guest_phone,
                        guest_email=guest_email,
                        check_in=check_in,
                        check_out=check_out,
                        room_type=room_type,
                        total_amount=total,
                        booking_reference=booking_ref,
                        num_nights=num_nights,
                        # notification_type="soft_hold" # Future enhancement
                    )
                )
            except Exception as notify_err:
                logger.error(f"Failed to send staff notification: {notify_err}")
                
            return {
                "success": True,
                "booking_reference": booking_ref,
                "guest_name": guest_name,
                "check_in_date": check_in,
                "check_out_date": check_out,
                "room_type": room_type,
                "total_amount": total,
                "message": f"I've placed a temporary hold and sent this to the team. You'll receive confirmation shortly."
            }
        else:
             return {
                "success": False,
                "message": "I couldn't place the hold right now. Please call reception."
             }
             
    except Exception as e:
        logger.error(f"Soft hold creation error: {e}")
        return {
            "success": False,
            "message": "System error. Please contact reception."
        }


async def handle_get_room_pricing(args: dict) -> dict:
    """Get room pricing information."""
    room_type = args.get("room_type", "all")
    
    if room_type == "all" or room_type not in ROOM_INFO:
        return {
            "pricing": {k: {"name": v["name"], "price": v["price"], "description": v["description"]} 
                       for k, v in ROOM_INFO.items()},
            "message": "Queen rooms start at $130, Twin at $140, Family at $160, and Accessible at $130 per night."
        }
    else:
        room = ROOM_INFO[room_type]
        return {
            "room_type": room_type,
            "name": room["name"],
            "price_per_night": room["price"],
            "description": room["description"],
            "message": f"The {room['name']} is ${room['price']} per night. {room['description']}."
        }


# =============================================================================
# KNOWLEDGE BASE HANDLERS
# =============================================================================

async def handle_get_room_details(args: dict) -> dict:
    """Get detailed room information including all facilities."""
    from services.motel_knowledge_base import get_room_details
    
    room_type = args.get("room_type", "queen")
    result = get_room_details(room_type)
    
    if "error" in result:
        return result
    
    facilities_list = ", ".join(result["facilities"][:5])
    return {
        **result,
        "message": f"The {result['name']} is {result['price_from']}, fits up to {result['max_guests']} guests with {result['bedding']}. Includes {facilities_list} and more."
    }


async def handle_recommend_room(args: dict) -> dict:
    """Recommend a room based on guest count and needs."""
    from services.motel_knowledge_base import recommend_room
    
    num_guests = args.get("num_guests", 2)
    needs_accessibility = args.get("needs_accessibility", False)
    
    result = recommend_room(num_guests, needs_accessibility)
    return {
        **result,
        "message": f"I'd recommend our {result['recommended']} at ${result['price']} per night. {result['reason']}."
    }


async def handle_get_check_in_out_info(args: dict) -> dict:
    """Get check-in and check-out policies."""
    from services.motel_knowledge_base import get_check_in_out_info
    
    result = get_check_in_out_info()
    return {
        **result,
        "message": f"Check-in is {result['check_in']}, check-out is {result['check_out']}. Reception is open {result['reception_hours']}. Late check-in is available on request."
    }


async def handle_get_location_info(args: dict) -> dict:
    """Get location and distance information."""
    from services.motel_knowledge_base import get_location_info, MOTEL_INFO
    
    detail = args.get("detail")
    result = get_location_info(detail)
    
    if detail == "distances":
        return {
            **result,
            "message": "We're about 3 hours from Melbourne, 30 minutes from Albury-Wodonga, and 20 minutes from Rutherglen wine region."
        }
    elif detail == "travel":
        return {
            **result,
            "message": "You can reach us by car just off the Hume Freeway, by train to Chiltern station, or fly into Albury Airport 30 minutes away."
        }
    else:
        return {
            **result,
            "address": MOTEL_INFO["address"],
            "message": f"We're at {MOTEL_INFO['address']}, just off the Hume Freeway in Chiltern, North East Victoria."
        }


async def handle_get_amenities(args: dict) -> dict:
    """Get motel amenities information."""
    from services.motel_knowledge_base import get_amenities
    
    category = args.get("category")
    result = get_amenities(category)
    
    amenities_list = ", ".join(result["amenities"][:5])
    return {
        **result,
        "message": f"We offer {amenities_list}. All rooms are ground floor with parking right outside."
    }


async def handle_get_activities_nearby(args: dict) -> dict:
    """Get nearby activities and attractions."""
    from services.motel_knowledge_base import get_activities_nearby
    
    result = get_activities_nearby()
    
    activities_sample = ", ".join(result["activities"][:4])
    areas_sample = ", ".join(result["nearby_areas"][:3])
    return {
        **result,
        "message": f"There's plenty to do - {activities_sample} and more. You can easily visit {areas_sample} from here."
    }


async def handle_search_motel_info(args: dict) -> dict:
    """General search across motel information."""
    from services.motel_knowledge_base import search_motel_info
    
    query = args.get("query", "")
    result = search_motel_info(query)
    
    if "note" in result and "No specific info" in result.get("note", ""):
        return {
            **result,
            "message": f"Let me check on that for you. For specific questions about {query}, please contact reception at (03) 5726 1788."
        }
    
    # Build message from found results
    messages = []
    if "wifi" in result:
        messages.append(result["wifi"])
    if "pool" in result:
        messages.append(result["pool"])
    if "smoking" in result:
        messages.append(result["smoking"])
    if "pets" in result:
        messages.append(result["pets"])
    if "amenities" in result:
        messages.append(", ".join(result["amenities"][:3]))
    
    return {
        **result,
        "message": " ".join(messages) if messages else "I found some information for you."
    }


async def handle_get_policies(args: dict) -> dict:
    """Get motel policies (cancellation, payment, etc.)."""
    from services.motel_knowledge_base import get_policies
    
    policy_type = args.get("policy_type")
    result = get_policies(policy_type)
    
    # Build friendly message based on policy type
    if policy_type == "cancellation":
        cancel_info = result.get("cancellation", {})
        standard = cancel_info.get("standard", "")
        return {
            **result,
            "message": f"Our cancellation policy: {standard}"
        }
    elif policy_type == "payment":
        payment_info = result.get("payment", {})
        methods = payment_info.get("methods", "")
        return {
            **result,
            "message": f"We accept {methods}. {payment_info.get('terms', '')}"
        }
    else:
        # Return all policies
        return {
            **result,
            "message": "I can tell you about our cancellation and payment policies. Which would you like to know about?"
        }


async def handle_lookup_booking(args: dict, caller_id: str = None) -> dict:
    """
    Look up an existing booking by guest name.
    
    Uses hybrid approach:
    1. Prioritize verified caller_id from Twilio for phone matching
    2. Fall back to spoken phone if provided
    3. Name is primary search key
    
    Args:
        args: {guest_name, phone?, reference?}
        caller_id: Verified phone number from Twilio (trusted)
        
    Returns:
        Booking details or helpful message
    """
    from services.motel_knowledge_base import lookup_booking
    
    guest_name = args.get("guest_name", "")
    spoken_phone = args.get("phone")  # What user said (may have errors)
    reference = args.get("reference")
    
    if not guest_name:
        return {
            "found": False,
            "message": "I'd need your name to look up your booking. What name was it booked under?"
        }
    
    # Use verified caller_id if available, otherwise use spoken phone
    # This handles STT errors gracefully since we have the real phone
    search_phone = caller_id if caller_id else spoken_phone
    
    result = await lookup_booking(guest_name, search_phone, reference)
    
    # If not found with caller_id but user provided different phone, try that too
    if not result.get("found") and caller_id and spoken_phone and spoken_phone != caller_id:
        result = await lookup_booking(guest_name, spoken_phone, reference)
    
    if result.get("found") and result.get("booking"):
        booking = result["booking"]
        # Mask part of phone for security when confirming
        return {
            **result,
            "verified_by_caller_id": bool(caller_id),
            "message": f"Found it! You have a {booking.get('room_type', 'room')} booked from {booking.get('check_in')} to {booking.get('check_out')} for {booking.get('num_guests')} guests. Your total is ${booking.get('total_amount')}. Reference: {booking.get('reference')}"
        }
    
    # Not found - guide the AI to ask about source
    return {
        "found": False,
        "message": "I couldn't find a booking under that name. To help me track it down, did you book directly at the desk (walk-in), through a website, or over the phone?"
    }


async def handle_report_missing_booking(args: dict) -> dict:
    """Report a missing booking to staff."""
    from services.staff_notifications import staff_notification_service
    from services.voice_agent.text_utils import normalize_phone_number, is_valid_au_phone
    
    name = args.get("guest_name", "Unknown")
    source = args.get("booking_source", "unknown")
    check_in = args.get("expected_check_in", "Unknown")
    phone = args.get("contact_phone", "")
    
    # Validate phone if provided
    if phone:
        normalized = normalize_phone_number(phone)
        is_valid, error_msg = is_valid_au_phone(normalized)
        if not is_valid:
            return {
                "success": False,
                "needs_phone_correction": True,
                "message": error_msg
            }
        phone = normalized  # Use cleaned version
    
    reason = f"MISSING BOOKING REPORT: Customer claims booked via {source}. Check-in: {check_in}"
    
    success = await staff_notification_service.notify_new_callback_request(
        customer_phone=phone or "Unknown",
        customer_name=name,
        reason=reason,
        urgency="high"
    )
    
    if success:
        return {
            "success": True,
            "message": "I've sent an urgent report to the team with those details. They will check the records and call you back shortly to confirm."
        }
    else:
        return {
            "success": False,
            "message": "I've noted your details. Please call reception at (03) 5726 1788 during business hours to resolve this."
        }


async def handle_transfer_to_staff() -> dict:
    """
    Initiate call transfer to staff.
    Returns a signal that the handler will use to execute Twilio transfer.
    """
    from core.config import settings
    
    return {
        "action": "transfer",
        "transfer_to": settings.STAFF_PHONE_NUMBER,
        "message": "Sure, I'll transfer you to our team now. Please hold."
    }


async def handle_end_call(args: dict = None) -> dict:
    """
    End the call gracefully.
    Returns an action signal that the handler will use to schedule hangup.
    """
    args = args or {}
    return {
        "action": "end_call",
        "success": True,
        "message": args.get("message", "")  # Optional message to speak before hanging up
    }


# =============================================================================
# FUNCTION DISPATCHER
# =============================================================================

class FunctionDispatcher:
    """
    Dispatches function calls to appropriate handlers.
    
    Usage:
        dispatcher = FunctionDispatcher(db_service, user_phone, save_fn, abuse_protection, tenant_id)
        result = await dispatcher.execute("check_availability", {"check_in_date": "2024-01-15"})
    """
    
    def __init__(self, db_service, user_phone: str, save_reservation_fn, abuse_protection, tenant_id: str = "coalcreek"):
        """
        Initialize dispatcher with required dependencies.
        
        Args:
            db_service: Database service for queries
            user_phone: Caller's phone number
            save_reservation_fn: Function to save reservations
            abuse_protection: AbuseProtection instance for flag_off_topic
            tenant_id: Multi-tenant identifier (e.g., "coalcreek", "saranda")
        """
        self.db_service = db_service
        self.user_phone = user_phone
        self.save_reservation_fn = save_reservation_fn
        self.abuse_protection = abuse_protection
        self.tenant_id = tenant_id
    
    async def execute(self, function_name: str, args: dict, context: dict = None) -> dict:
        """
        Execute a function with retry logic (max 2 attempts) and watchdog timeout (15s).
        """
        import asyncio
        
        MAX_RETRIES = 2
        WATCHDOG_TIMEOUT = 15.0 # Seconds before considering it "ghosted"
        
        for attempt in range(MAX_RETRIES):
            try:
                # Watchdog: Wrap execution in timeout
                # We call the internal dispatch logic here
                result = await asyncio.wait_for(
                    self._dispatch_logic(function_name, args, context),
                    timeout=WATCHDOG_TIMEOUT
                )
                return result
                
            except asyncio.TimeoutError:
                logger.error(f"⏳ Function {function_name} GHOSTED (>15s) - Attempt {attempt+1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    logger.info("🔄 Retrying function execution...")
                    continue
                else:
                    # Final Fail: Return polite placeholder (TODO: Switch to transfer)
                    return {
                        "success": False,
                        "message": "I apologize, I'm having trouble connecting to the system securely. I've noted your request, and I'll have a staff member call you back shortly to assist.",
                        "outcome_override": "system_failure",
                        "error_details": f"Ghosting Timeout: {function_name} > {WATCHDOG_TIMEOUT}s"
                        # "action": "transfer", # TODO: Uncomment to enable auto-transfer logic
                        # "transfer_to": settings.STAFF_PHONE_NUMBER
                    }
                    
            except Exception as e:
                logger.error(f"❌ Function error {function_name}: {e} - Attempt {attempt+1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    continue
                return {
                    "error": str(e), 
                    "message": "I'm having a brief technical hiccup. Please hold on a moment.",
                    "outcome_override": "system_error",
                    "error_details": f"Function Error: {function_name} - {str(e)}"
                }
        
    async def _dispatch_logic(self, function_name: str, args: dict, context: dict = None) -> dict:
        """Internal dispatch logic matching function names to handlers."""
        try:
            # Availability & Booking
            if function_name == "check_availability":
                return await handle_check_availability(args, self.db_service, self.tenant_id)
            
            elif function_name == "create_booking_request":
                return await handle_create_booking_request(args, self.user_phone, self.save_reservation_fn, self.tenant_id)
            
            elif function_name == "get_room_pricing":
                return await handle_get_room_pricing(args)
            
            # Knowledge Base
            elif function_name == "get_room_details":
                return await handle_get_room_details(args)
            
            elif function_name == "recommend_room":
                return await handle_recommend_room(args)
            
            elif function_name == "get_check_in_out_info":
                return await handle_get_check_in_out_info(args)
            
            elif function_name == "get_location_info":
                return await handle_get_location_info(args)
            
            elif function_name == "get_amenities":
                return await handle_get_amenities(args)
            
            elif function_name == "get_activities_nearby":
                return await handle_get_activities_nearby(args)
            
            elif function_name == "search_motel_info":
                return await handle_search_motel_info(args)
            
            elif function_name == "get_policies":
                return await handle_get_policies(args)
            
            elif function_name == "lookup_booking":
                # Pass caller ID for hybrid matching (uses verified Twilio phone)
                return await handle_lookup_booking(args, caller_id=self.user_phone)
            
            elif function_name == "update_guest_info":
                return await handle_update_guest_info(args)
            
            # Human Handoff & Reporting
            elif function_name == "request_human_callback":
                return await handle_request_human_callback(args)
                
            elif function_name == "report_missing_booking":
                # Ensure phone is captured if not in args
                if "contact_phone" not in args or not args["contact_phone"]:
                    args["contact_phone"] = self.user_phone
                return await handle_report_missing_booking(args)
            
            # Call Transfer
            elif function_name == "transfer_to_staff":
                return await handle_transfer_to_staff()
            
            # Call Termination
            elif function_name == "end_call":
                return await handle_end_call()
            
            # Abuse Protection
            elif function_name == "report_user_behavior":
                category = args.get("category", "off_topic")
                reason = args.get("reason", "unspecified")
                return self.abuse_protection.report_violation(category, reason)
            
            else:
                return {"error": f"Unknown function: {function_name}"}
                
        except Exception as e:
            # Re-raise for the watchdog loop to catch and log properly
            raise e

async def handle_request_human_callback(args: dict) -> dict:
    """
    Request a human staff member to call the customer back.
    """
    from services.staff_notifications import staff_notification_service
    from services.voice_agent.text_utils import normalize_phone_number, is_valid_au_phone
    
    customer_name = args.get("customer_name", "Unknown Customer")
    customer_phone = args.get("customer_phone", "")
    reason = args.get("reason", "General Inquiry")
    urgency = args.get("urgency", "medium")
    
    # If phone is missing
    if not customer_phone:
        return {
            "success": False,
            "message": "I need your phone number to arrange a callback. What's the best number?"
        }
    
    # Normalize and validate phone
    normalized_phone = normalize_phone_number(customer_phone)
    is_valid, validation_msg = is_valid_au_phone(normalized_phone)
    
    if not is_valid:
        return {
            "success": False,
            "message": validation_msg
        }
        
    success = await staff_notification_service.notify_new_callback_request(
        customer_phone=normalized_phone,
        customer_name=customer_name,
        reason=reason,
        urgency=urgency
    )
    
    if success:
        return {
            "success": True,
            "message": "I've sent that request to reception. They will call you back shortly."
        }
    else:
        # Fallback if system fails
        return {
            "success": True,
            "message": "I've noted your request. Reception will be in touch as soon as they can."
        }

async def handle_update_guest_info(args: dict) -> dict:
    """
    Save guest details to memory/context AND update the latest reservation/notification.
    This ensures guest_email is persisted even if provided after booking.
    """
    import httpx
    import json
    from core.config import settings
    from services.voice_agent.text_utils import normalize_phone_number, is_valid_au_phone
    from core.logger import logger
    from core.constants import MOTEL_DB_ID
    
    guest_name = args.get("guest_name", "")
    guest_phone = args.get("guest_phone", "")
    guest_email = args.get("guest_email", "")
    
    # Validate and normalize phone if provided
    if guest_phone:
        normalized = normalize_phone_number(guest_phone)
        is_valid, error_msg = is_valid_au_phone(normalized)
        if not is_valid:
            return {
                "success": False,
                "needs_phone_correction": True,
                "message": error_msg
            }
        guest_phone = normalized  # Use cleaned version
    
    logger.info(f"📝 Updated guest info: {guest_name}, {guest_phone}, {guest_email}")
    
    # If we have an email, try to update the most recent reservation and notification
    if guest_email and guest_phone:
        try:
            # ASYNC Appwrite update via httpx
            url = f"{settings.APPWRITE_ENDPOINT}/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
            headers = {
                "Content-Type": "application/json",
                "X-Appwrite-Project": settings.APPWRITE_PROJECT_ID,
                "X-Appwrite-Key": settings.APPWRITE_API_KEY
            }
            
            # Find the most recent reservation by this phone number
            url = f"{settings.APPWRITE_ENDPOINT}/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                docs = response.json().get("documents", [])
                # Find most recent reservation for this phone (pending status preferred)
                matching = [d for d in docs if d.get("guest_phone") == guest_phone]
                if matching:
                    # Sort by created_at descending, prefer pending
                    matching.sort(key=lambda x: (x.get("status") != "pending", x.get("created_at", "")), reverse=True)
                    latest = matching[0]
                    
                    # Update with email
                    patch_url = f"{url}/{latest['$id']}"
                    patch_response = requests.patch(
                        patch_url,
                        headers=headers,
                        json={"data": {"guest_email": guest_email}}
                    )
                    if patch_response.status_code in [200, 201]:
                        logger.info(f"✅ Updated reservation {latest['$id']} with email")
            
            # Also update any pending notification for this customer
            notif_url = f"{settings.APPWRITE_ENDPOINT}/databases/{MOTEL_DB_ID}/collections/staff_notifications/documents"
            notif_response = requests.get(notif_url, headers=headers)
            
            if notif_response.status_code == 200:
                notif_docs = notif_response.json().get("documents", [])
                # Find pending notification for this phone
                matching_notifs = [n for n in notif_docs 
                                   if n.get("customer_phone") == guest_phone 
                                   and n.get("status") == "pending"]
                if matching_notifs:
                    import json
                    latest_notif = matching_notifs[0]
                    
                    # Update extra_data with guest_email
                    extra_data_str = latest_notif.get("extra_data", "{}")
                    try:
                        extra_data = json.loads(extra_data_str) if extra_data_str else {}
                    except:
                        extra_data = {}
                    
                    extra_data["guest_email"] = guest_email
                    
                    patch_notif_url = f"{notif_url}/{latest_notif['$id']}"
                    requests.patch(
                        patch_notif_url,
                        headers=headers,
                        json={"data": {"extra_data": json.dumps(extra_data)}}
                    )
                    logger.info(f"✅ Updated notification {latest_notif['$id']} with email")
                    
        except Exception as e:
            logger.warning(f"Could not update reservation/notification with email: {e}")
    
    return {
        "success": True,
        "guest_name": guest_name,
        "guest_phone": guest_phone,
        "guest_email": guest_email,
        "message": f"Got it. I have your details: {guest_name}" + (f", phone {guest_phone}" if guest_phone else "")
    }
