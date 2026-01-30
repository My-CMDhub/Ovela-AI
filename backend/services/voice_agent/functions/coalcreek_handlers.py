"""
Coal Creek Motel Function Handlers
=================================
Booking request and information handlers for Coal Creek Motel.

Key Design:
- Uses "Read-Only + Soft Hold" strategy
- Fetches data from `services.motel_knowledge_base` with `tenant_id="coalcreek"`
- Directly implements specific handlers like `handle_create_booking_request`
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Import knowledge base services
from services.motel_knowledge_base import (
    get_room_pricing, get_room_details, recommend_room,
    get_check_in_out_info, get_location_info, get_amenities,
    get_activities_nearby, search_motel_info, get_policies,
    set_tenant_context
)
from services.knowledge_base.coalcreek import COALCREEK_DATA

logger = logging.getLogger(__name__)


# =============================================================================
# BOOKING HANDLERS (Read-Only + Soft Hold)
# =============================================================================

async def handle_check_availability(args: dict, db_service) -> dict:
    """
    Check room availability.
    
    Strategy: 
    1. If PMS configured → Real-time check (VERIFIED)
    2. If PMS unavailable → Fallback to "unverified" (staff confirms)
    """
    # Ensure KB knows we are acting as Coal Creek
    set_tenant_context("coalcreek")
    
    from services.pms import get_pms_client, is_pms_configured
    
    check_in = args.get("check_in_date", "")
    check_out = args.get("check_out_date", "")
    room_type = args.get("room_type", "queen")
    
    if not check_in:
        return {"available": False, "verified": False, "message": "Please provide check-in date"}
    
    # 1. Basic Date Validation
    try:
        check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
        if check_in_dt.date() < datetime.now().date():
            return {
                "available": False,
                "verified": True,
                "message": "That date has already passed. What dates were you looking at?"
            }
    except ValueError:
        return {
            "available": False,
            "verified": False,
            "message": "I didn't catch the date properly. Could you repeat that?"
        }

    # 2. Check if PMS is configured for real-time verification
    if is_pms_configured("coalcreek"):
        pms = get_pms_client("coalcreek")
        
        try:
            # Real-time PMS check
            result = await pms.check_availability(check_in, check_out, room_type)
            
            if result.is_verified:
                # PMS confirmed availability
                return {
                    "available": result.available,
                    "rooms_left": result.rooms_left,
                    "verified": True,
                    "room_type": room_type,
                    "check_in_date": check_in,
                    "message": f"I've checked our booking system and {room_type} rooms are {'available' if result.available else 'fully booked'} for those dates."
                }
        except Exception as e:
            logger.error(f"PMS availability check failed: {e}")
            # Fall through to unverified fallback

    # 3. Fallback: Unverified (PMS not configured or failed)
    # Get room data from KB for pricing
    rooms_data = COALCREEK_DATA["rooms"]
    
    # Simple key matching
    key_map = {
        "queen": "queen",
        "standard": "queen",
        "twin": "twin",
        "family": "family",
        "spa": "spa",
        "deluxe": "spa"
    }
    
    search_key = room_type.lower().split()[0]  # First word
    final_key = key_map.get(search_key, "queen")
    target_room = rooms_data.get(final_key, rooms_data["queen"])

    # "Soft Hold" messaging - staff will verify
    return {
        "available": "unknown",
        "verified": False,
        "room_type": target_room["name"],
        "price_per_night": target_room["price"],
        "check_in_date": check_in,
        "message": f"I'll need to check with the team on availability for the {target_room['name']}. Can I take your details and have someone confirm?"
    }


async def handle_create_booking_request(args: dict, user_phone: str, save_reservation_fn) -> dict:
    """
    Create a SOFT HOLD booking request.
    Status: pending_confirmation
    """
    guest_name = args.get("guest_name", "")
    check_in = args.get("check_in_date", "")
    check_out = args.get("check_out_date", "")
    room_type = args.get("room_type", "queen")
    num_guests = args.get("num_guests", 1)
    guest_email = args.get("guest_email", "")
    notes = args.get("notes", "")
    
    guest_phone = args.get("guest_phone", "") or user_phone
    
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
            
    # Get pricing (Approximate for hold)
    rooms_data = COALCREEK_DATA["rooms"]
    # fuzzy match logic again
    search_key = room_type.lower().split()[0]
    key_map = {"queen": "queen", "standard": "queen", "twin": "twin", "family": "family", "spa": "spa", "deluxe": "spa"}
    final_key = key_map.get(search_key, "queen")
    room_data = rooms_data.get(final_key, rooms_data["queen"])
    
    rate = room_data["price"]
    total = rate * num_nights
    
    # Booking Ref
    booking_ref = f"CC-{int(time.time()) % 100000:05d}"
    now = datetime.now().isoformat()
    
    reservation_data = {
        "guest_name": guest_name,
        "guest_phone": guest_phone,
        "guest_email": guest_email,
        "num_guests": num_guests,
        "room_type": room_data["name"],
        "check_in_date": check_in,
        "check_out_date": check_out,
        "num_nights": num_nights,
        "rate_per_night": rate,
        "total_amount": total,
        "status": "pending_confirmation", # Explicit Soft Hold status
        "source": "voice_ai_soft_hold",
        "booking_reference": booking_ref,
        "notes": notes or "Soft Hold Request via AI",
        "created_at": now,
        "updated_at": now,
        "created_by": "ovela_ai",
        "tenant_id": "coalcreek"
    }
    
    try:
        # Save to DB (if saving function provided)
        if save_reservation_fn:
            save_reservation_fn(reservation_data)
        
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
                    room_type=room_data["name"],
                    total_amount=total,
                    booking_reference=booking_ref,
                    num_nights=num_nights,
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
            "room_type": room_data["name"],
            "total_amount": total,
            "message": f"I've placed a temporary hold and sent this to the team. They'll email you a payment link shortly to confirm."
        }

    except Exception as e:
        logger.error(f"Soft hold creation error: {e}")
        return {
            "success": False,
            "message": "System error. Please contact reception."
        }


# =============================================================================
# HUMAN & UTILITY HANDLERS
# =============================================================================

async def handle_report_missing_booking(args: dict, user_phone: str) -> dict:
    """Report a missing booking to staff."""
    from services.staff_notifications import staff_notification_service
    from services.voice_agent.text_utils import normalize_phone_number
    
    name = args.get("guest_name", "Unknown")
    source = args.get("booking_source", "unknown")
    check_in = args.get("expected_check_in", "Unknown")
    contact_phone = args.get("contact_phone", "") or user_phone
    
    try:
        contact_phone = normalize_phone_number(contact_phone)
    except:
        pass # Ignore errors if utils fail
    
    reason = f"MISSING BOOKING: Guest claims {source} booking. Check-in: {check_in}"
    
    await staff_notification_service.notify_new_callback_request(
        customer_phone=contact_phone,
        customer_name=name,
        reason=reason,
        urgency="high"
    )
    
    return {
        "success": True,
        "message": "I've sent an urgent report to the team. They will checks the records and call you back shortly."
    }

async def handle_request_human_callback(args: dict, user_phone: str) -> dict:
    """Request a human callback."""
    from services.staff_notifications import staff_notification_service
    from services.voice_agent.text_utils import normalize_phone_number
    
    customer_name = args.get("customer_name", "Unknown")
    customer_phone = args.get("customer_phone", "") or user_phone
    reason = args.get("reason", "Inquiry")
    
    try:
        customer_phone = normalize_phone_number(customer_phone)
    except:
        pass
        
    await staff_notification_service.notify_new_callback_request(
        customer_phone=customer_phone,
        customer_name=customer_name,
        reason=reason,
        urgency="medium"
    )
    
    return {
        "success": True,
        "message": "I've passed your details to reception. They'll give you a call back soon."
    }


async def handle_update_guest_info(args: dict, db_service) -> dict:
    """
    Save guest details to CRM for persistent memory.
    Call this when guest verifies their info.
    """
    guest_name = args.get("guest_name", "")
    guest_phone = args.get("guest_phone", "")
    guest_email = args.get("guest_email", "")
    
    logger.info(f"Captured Guest Info: {guest_name} - {guest_phone}")
    
    if db_service and hasattr(db_service, "upsert_motel_guest"):
        try:
            # Save as 'inquiry' since they haven't booked yet (just memory)
            # If they book later, the booking logic should upgrade this or we can add a 'create_booking' hook.
            # But upsert is safe.
            db_service.upsert_motel_guest(
                guest_name=guest_name, 
                guest_phone=guest_phone, 
                guest_email=guest_email,
                tenant_id="coalcreek",
                status="inquiry"
            )
            message = "Details securely saved to guest profile."
        except Exception as e:
            logger.error(f"Failed to save guest info: {e}")
            message = "Details captured."
    else:
        message = "Details captured (temporary)."
        
    return {"success": True, "message": message}


# =============================================================================
# COAL CREEK DISPATCHER
# =============================================================================

class CoalCreekFunctionDispatcher:
    """
    Dispatches Coal Creek specific function calls.
    Ensures 'coalcreek' context is set for all KB operations.
    """
    
    def __init__(self, db_service, user_phone: str, save_reservation_fn, abuse_protection):
        self.db_service = db_service
        self.user_phone = user_phone
        self.save_reservation_fn = save_reservation_fn
        self.abuse_protection = abuse_protection
        # Always set context on init
        set_tenant_context("coalcreek")
    
    async def execute(self, function_name: str, args: dict, context: dict = None) -> dict:
        """Execute a function with basic error handling."""
        import asyncio
        TIMEOUT = 10.0
        
        # Refresh context just in case
        set_tenant_context("coalcreek")
        
        try:
             result = await asyncio.wait_for(
                self._dispatch(function_name, args, context),
                timeout=TIMEOUT
             )
             return result
        except asyncio.TimeoutError:
             logger.error(f"Function {function_name} timed out")
             return {"success": False, "message": "I'm having a connection issue. One moment."}
        except Exception as e:
             logger.error(f"Function error {function_name}: {e}")
             return {"error": str(e), "message": "I encountered a system error."}

    async def _dispatch(self, function_name: str, args: dict, context: dict = None) -> dict:
        """Internal dispatch map."""
        
        # Booking / Availability
        if function_name == "check_availability":
            return await handle_check_availability(args, self.db_service)
        
        elif function_name == "create_booking_request":
            return await handle_create_booking_request(args, self.user_phone, self.save_reservation_fn)
            
        elif function_name == "lookup_booking":
            # For trial, return the generic "not connected" message
            return {
                "found": False,
                "message": "I don't have access to the main booking calendar right now. If you have a confirmation email, I can forward your details to reception?"
            }
        
        # Knowledge Base (Direct calls to motel_knowledge_base service)
        elif function_name == "get_room_pricing":
             return get_room_pricing(args.get("room_type"))
             
        elif function_name == "get_room_details":
             return get_room_details(args.get("room_type", "queen"))
             
        elif function_name == "recommend_room":
             return recommend_room(args.get("num_guests", 2), args.get("needs_accessibility", False))
             
        elif function_name == "get_check_in_out_info":
             return get_check_in_out_info()
             
        elif function_name == "get_location_info":
             return get_location_info(args.get("detail"))
             
        elif function_name == "get_amenities":
             return get_amenities(args.get("category"))
             
        elif function_name == "get_activities_nearby":
             return get_activities_nearby()
             
        elif function_name == "search_motel_info":
             return search_motel_info(args.get("query", ""))
             
        elif function_name == "get_policies":
             return get_policies(args.get("policy_type"))
             
        # Human / Reporting
        elif function_name == "request_human_callback":
             return await handle_request_human_callback(args, self.user_phone)
             
        elif function_name == "report_missing_booking":
             return await handle_report_missing_booking(args, self.user_phone)
             
        elif function_name == "update_guest_info":
             return await handle_update_guest_info(args, self.db_service)
             
        # Common controls
        elif function_name == "end_call":
             return {"action": "end_call", "success": True, "message": args.get("message", "")}
             
        elif function_name == "transfer_to_staff":
             from core.config import settings
             return {
                "action": "transfer",
                "transfer_to": settings.STAFF_PHONE_NUMBER,
                "message": "Sure, I'll transfer you to reception now."
            }
            
        elif function_name == "report_user_behavior":
             if self.abuse_protection:
                 category = args.get("category", "off_topic")
                 reason = args.get("reason", "unspecified")
                 return self.abuse_protection.report_violation(category, reason)
             return {"message": "Please continue."}
        
        else:
             return {"error": f"Unknown function: {function_name}"}
