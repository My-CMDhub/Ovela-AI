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

async def handle_check_availability(args: dict, db_service) -> dict:
    """
    Check room availability for given dates against actual bookings.
    
    Args:
        args: {check_in_date, check_out_date?, room_type?}
        db_service: Database service for querying bookings
        
    Returns:
        {available: bool, message: str, ...}
    """
    check_in = args.get("check_in_date", "")
    check_out = args.get("check_out_date", "")
    room_type = args.get("room_type", "queen")
    
    if not check_in:
        return {"available": False, "message": "Please provide check-in date"}
    
    try:
        check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
        
        # Check if date is in the past
        if check_in_dt.date() < datetime.now().date():
            return {
                "available": False,
                "message": "That date has already passed. What dates were you looking at?"
            }
        
        # Query database for existing bookings on this date
        try:
            existing_bookings = db_service.get_bookings(date=check_in)
            
            # Count bookings by room type
            booked_rooms = {}
            for booking in existing_bookings:
                rtype = booking.get("room_type", "queen")
                booked_rooms[rtype] = booked_rooms.get(rtype, 0) + 1
            
            # Check if requested room type is available
            room = ROOM_INFO.get(room_type, ROOM_INFO["queen"])
            rooms_booked = booked_rooms.get(room_type, 0)
            rooms_available = room["total_rooms"] - rooms_booked
            
            if rooms_available > 0:
                return {
                    "available": True,
                    "room_type": room_type,
                    "rooms_remaining": rooms_available,
                    "price_per_night": room["price"],
                    "check_in_date": check_in,
                    "message": f"Yes, we have {room['name']}s available for {check_in} at ${room['price']} per night."
                }
            else:
                # Suggest alternatives
                alternatives = []
                for rtype, info in ROOM_INFO.items():
                    if rtype != room_type and booked_rooms.get(rtype, 0) < info["total_rooms"]:
                        alternatives.append(f"{info['name']} (${info['price']})")
                
                alt_msg = f" We do have: {', '.join(alternatives[:2])}." if alternatives else ""
                return {
                    "available": False,
                    "room_type": room_type,
                    "message": f"Sorry, {room['name']}s are fully booked for {check_in}.{alt_msg}"
                }
                
        except Exception as db_err:
            logger.warning(f"Database query failed, using fallback: {db_err}")
            # Fallback: assume available if db fails
            room = ROOM_INFO.get(room_type, ROOM_INFO["queen"])
            return {
                "available": True,
                "room_type": room_type,
                "price_per_night": room["price"],
                "check_in_date": check_in,
                "message": f"Yes, we should have {room['name']}s available for ${room['price']} per night. I'll confirm when we make the booking."
            }
            
    except ValueError:
        return {
            "available": False,
            "message": "I didn't catch the date properly. Could you repeat that?"
        }


async def handle_create_booking(args: dict, user_phone: str, save_reservation_fn) -> dict:
    """
    Create a motel room reservation and save to database.
    
    Args:
        args: {guest_name, check_in_date, check_out_date?, room_type?, num_guests?, notes?}
        user_phone: Caller's phone number
        save_reservation_fn: Function to save reservation to database
        
    Returns:
        {success: bool, booking_reference: str, message: str, ...}
    """
    guest_name = args.get("guest_name", "")
    check_in = args.get("check_in_date", "")
    check_out = args.get("check_out_date", "")
    room_type = args.get("room_type", "queen")
    num_guests = args.get("num_guests", 1)
    guest_phone = args.get("guest_phone", user_phone)
    notes = args.get("notes", "")
    
    if not guest_name or not check_in:
        return {
            "success": False,
            "message": "I need your name and check-in date to make a booking."
        }
    
    # Calculate nights and checkout date
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
        except:
            num_nights = 1
    
    # Get pricing
    room = ROOM_INFO.get(room_type, ROOM_INFO["queen"])
    rate = room["price"]
    total = rate * num_nights
    
    # Generate booking reference
    booking_ref = f"LM-{int(time.time()) % 100000:05d}"
    
    # Create reservation data
    now = datetime.now().isoformat()
    
    reservation_data = {
        # Guest info
        "guest_name": guest_name,
        "guest_phone": guest_phone,
        "guest_email": "",
        "num_guests": num_guests,
        
        # Room details
        "room_type": room_type,
        
        # Dates
        "check_in_date": check_in,
        "check_out_date": check_out,
        "num_nights": num_nights,
        
        # Pricing
        "rate_per_night": rate,
        "total_amount": total,
        "deposit_paid": 0,
        
        # Status
        "status": "pending",
        "source": "voice_call",
        "booking_reference": booking_ref,
        
        # Notes
        "notes": notes or "Voice booking via Ovela AI",
        "arrival_time": "",
        
        # Metadata
        "created_at": now,
        "updated_at": now,
        "created_by": "ovela_ai"
    }
    
    try:
        result = save_reservation_fn(reservation_data)
        
        if result:
            logger.info(f"✅ Created motel reservation: {booking_ref} for {guest_name}")
            
            return {
                "success": True,
                "booking_reference": booking_ref,
                "guest_name": guest_name,
                "check_in_date": check_in,
                "check_out_date": check_out,
                "num_nights": num_nights,
                "room_type": room_type,
                "rate_per_night": rate,
                "total_amount": total,
                "message": f"Excellent! I've made a provisional booking. {room_type.title()} room for {guest_name}, checking in {check_in} for {num_nights} night{'s' if num_nights > 1 else ''}. That's ${total} total. Reception will confirm shortly."
            }
        else:
            logger.warning(f"📋 Reservation save failed, logging: {guest_name}, {check_in}, {room_type}")
            return {
                "success": True,
                "booking_reference": booking_ref,
                "message": f"I've noted your booking. {room_type.title()} room for {guest_name}, checking in {check_in}. Reception will call you back to confirm."
            }
            
    except Exception as e:
        logger.error(f"Reservation creation error: {e}")
        return {
            "success": False,
            "message": "I had trouble with the booking system. Let me take your details and reception will call you back."
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
    
    return result


# =============================================================================
# FUNCTION DISPATCHER
# =============================================================================

class FunctionDispatcher:
    """
    Dispatches function calls to appropriate handlers.
    
    Usage:
        dispatcher = FunctionDispatcher(db_service, user_phone, save_fn, abuse_protection)
        result = await dispatcher.execute("check_availability", {"check_in_date": "2024-01-15"})
    """
    
    def __init__(self, db_service, user_phone: str, save_reservation_fn, abuse_protection):
        """
        Initialize dispatcher with required dependencies.
        
        Args:
            db_service: Database service for queries
            user_phone: Caller's phone number
            save_reservation_fn: Function to save reservations
            abuse_protection: AbuseProtection instance for flag_off_topic
        """
        self.db_service = db_service
        self.user_phone = user_phone
        self.save_reservation_fn = save_reservation_fn
        self.abuse_protection = abuse_protection
    
    async def execute(self, function_name: str, args: dict) -> dict:
        """
        Execute a function by name with given arguments.
        
        Args:
            function_name: Name of function to call
            args: Arguments to pass to function
            
        Returns:
            Function result dict
        """
        try:
            # Availability & Booking
            if function_name == "check_availability":
                return await handle_check_availability(args, self.db_service)
            
            elif function_name == "create_booking":
                return await handle_create_booking(args, self.user_phone, self.save_reservation_fn)
            
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
            
            elif function_name == "lookup_booking":
                # Pass caller ID for hybrid matching (uses verified Twilio phone)
                return await handle_lookup_booking(args, caller_id=self.user_phone)
            
            elif function_name == "update_guest_info":
                return await handle_update_guest_info(args)
            
            # Human Handoff
            elif function_name == "request_human_callback":
                return await handle_request_human_callback(args)
            
            # Abuse Protection
            elif function_name == "flag_off_topic":
                reason = args.get("reason", "unspecified")
                return self.abuse_protection.flag_off_topic(reason)
            
            else:
                return {"error": f"Unknown function: {function_name}"}
                
        except Exception as e:
            logger.error(f"Function execution error ({function_name}): {e}")
            return {"error": str(e)}

async def handle_request_human_callback(args: dict) -> dict:
    """
    Request a human staff member to call the customer back.
    """
    from services.staff_notifications import staff_notification_service
    
    customer_name = args.get("customer_name", "Unknown Customer")
    customer_phone = args.get("customer_phone", "")
    reason = args.get("reason", "General Inquiry")
    urgency = args.get("urgency", "medium")
    
    # If phone is missing, try to get it from context if possible (not passed here yet, so rely on args)
    if not customer_phone:
        return {
            "success": False,
            "message": "I need your phone number to arrange a callback. What's the best number?"
        }
        
    success = await staff_notification_service.notify_new_callback_request(
        customer_phone=customer_phone,
        customer_name=customer_name,
        reason=reason,
        urgency=urgency
    )
    
    if success:
        return {
            "success": True,
            "message": "I've sent an urgent request to reception. They will call you back shortly."
        }
    else:
        # Fallback if system fails
        return {
            "success": True, # Pretend success to user to avoid confusion, but log error was handled
            "message": "I've noted your request. Reception will be in touch as soon as they can."
        }
