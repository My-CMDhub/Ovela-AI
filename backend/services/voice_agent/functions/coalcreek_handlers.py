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
import asyncio

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
    Check room availability using real-time scraping.
    
    Features:
    - Multi-night validation (checks EACH night)
    - Efficient data handling (minimal context)
    - Dead air prevention compatible (function designed for 3-10s latency)
    
    Returns compact result for AI to parse quickly.
    """
    # Ensure KB knows we are acting as Coal Creek
    set_tenant_context("coalcreek")
    
    check_in = args.get("check_in_date", "")
    check_out = args.get("check_out_date", "")
    room_type_arg = args.get("room_type", "any")
    
    if not check_in:
        return {
            "available": False, 
            "verified": False, 
            "message": "Please provide check-in date",
            "ai_should_say": "What date were you looking to check in?"
        }
    
    # 1. Basic Date Validation
    try:
        check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
        if check_in_dt.date() < datetime.now().date():
            return {
                "available": False,
                "verified": True,
                "message": "Date in the past",
                "ai_should_say": "That date has already passed. What dates were you looking at?"
            }
    except ValueError:
        return {
            "available": False,
            "verified": False,
            "message": "Invalid date format",
            "ai_should_say": "I didn't catch the date properly. Could you repeat that in month-day format?"
        }
    
    # Set checkout if not provided (1 night)
    if not check_out:
        check_out = (check_in_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Calculate nights
    try:
        check_out_dt = datetime.strptime(check_out, "%Y-%m-%d")
        nights = (check_out_dt - check_in_dt).days
        if nights < 1:
            nights = 1
            check_out = (check_in_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    except:
        nights = 1
        check_out = (check_in_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 2. Map room type to scraper format
    room_map = {
        "queen": "Queen/Double",
        "standard": "Queen/Double",
        "twin": "Twin Room",
        "family": "Family Suite",
        "suite": "Deluxe Spa Suite",
        "spa": "Deluxe Spa Suite",
        "deluxe": "Deluxe Spa Suite",
        "any": None  # Check all rooms
    }
    
    search_key = room_type_arg.lower()
    target_room = room_map.get(search_key)
    
    # 3. Call multi-night scraper with RETRY LOGIC (Max 2 Attempts)
    try:
        # Import the scraper
        import sys
        from scripts.test_multinight_availability import check_multinight_availability
        
        logger.info(f"🔍 Checking availability: {check_in} to {check_out} ({nights} nights), room={target_room or 'any'}")
        
        result = None
        MAX_RETRIES = 2
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Call the scraper
                result = await check_multinight_availability(
                    check_in_str=check_in,
                    check_out_str=check_out,
                    room_type=target_room
                )
                
                if result.get("success"):
                    logger.info(f"✅ Scraping success on attempt {attempt}")
                    break
                else:
                    logger.warning(f"⚠️ Scraping attempt {attempt} failed: {result.get('error')}")
                    
            except Exception as scrape_err:
                logger.error(f"⚠️ Scraping exception on attempt {attempt}: {scrape_err}")
                result = {"success": False, "error": str(scrape_err)}
            
            # Small delay before retry if not last attempt
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1.0)
        
        # Check final result
        if not result or not result.get("success"):
            # Scraping failed after retries - TRANSPARENT FALLBACK
            logger.error(f"❌ All scraping attempts failed. Triggering fallback.")
            return {
                "available": "unknown",
                "verified": False,
                "message": "Technical issue accessing live calendar",
                "ai_should_say": "Sorry, I can't access the live calendar right now. I'll transfer you to reception."
            }
        
        # 4. Parse result efficiently
        available_all_nights = result.get("available_all_nights", False)
        blocked_dates = result.get("blocked_dates", [])
        available_rooms = result.get("available_rooms", [])
        
        # 5. Build compact AI response
        if available_all_nights and target_room:
            # Specific room is available
            # Get pricing from first night
            first_night_data = result.get("per_night_results", {})
            first_date = list(first_night_data.keys())[0] if first_night_data else None
            price = None
            
            if first_date:
                for room in first_night_data[first_date]:
                    if room.get("room_type") == target_room:
                        price = room.get("price_per_night")
                        break
            
            return {
                "available": True,
                "verified": True,
                "room_type": target_room,
                "check_in": check_in,
                "check_out": check_out,
                "nights": nights,
                "price_per_night": price,
                "total": price * nights if price else None,
                "ai_should_say": f"Great news! The {target_room} is available for {check_in if nights == 1 else f'{nights} nights from {check_in}'}. The rate is ${price} per night{f', total ${price * nights}' if nights > 1 else ''}. Would you like me to place a hold?"
            }
            
        elif available_all_nights and not target_room:
            # Guest asked for "any" room - show what's available
            prices = {}
            first_night_data = result.get("per_night_results", {})
            first_date = list(first_night_data.keys())[0] if first_night_data else None
            
            if first_date:
                for room in first_night_data[first_date]:
                    room_name = room.get("room_type")
                    if room_name in available_rooms:
                        prices[room_name] = room.get("price_per_night")
            
            room_list = ", ".join([f"{r} (${prices.get(r)}/night)" for r in available_rooms if r in prices])
            
            return {
                "available": True,
                "verified": True,
                "available_rooms": available_rooms,
                "check_in": check_in,
                "check_out": check_out,
                "nights": nights,
                "rooms_with_pricing": prices,
                "ai_should_say": f"I have {len(available_rooms)} room types available for those dates: {room_list}. Which would you prefer?"
            }
            
        else:
            # NOT available - explain why
            if target_room:
                # Specific room requested but blocked
                blocked_str = ", ".join(blocked_dates)
                return {
                    "available": False,
                    "verified": True,
                    "room_type": target_room,
                    "blocked_dates": blocked_dates,
                    "check_in": check_in,
                    "check_out": check_out,
                    "nights": nights,
                    "ai_should_say": f"I'm sorry, the {target_room} isn't available for all {nights} night{'s' if nights > 1 else ''} - it's sold out on {blocked_str}. However, I have other room types available. Would you like to hear those options?"
                }
            else:
                # All rooms sold out
                blocked_str = ", ".join(blocked_dates)
                return {
                    "available": False,
                    "verified": True,
                    "blocked_dates": blocked_dates,
                    "check_in": check_in,
                    "check_out": check_out,
                    "nights": nights,
                    "ai_should_say": f"I'm sorry, we're fully booked on {blocked_str}. Would you like to check different dates, or can I have someone call you if we get a cancellation?"
                }
        
    except Exception as e:
        logger.error(f"Availability check error: {e}", exc_info=True)
        return {
            "available": "unknown",
            "verified": False,
            "error": str(e),
            "ai_should_say": "Sorry, I can't check availability right now. I'll transfer you to reception."
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
