"""
The Lydoun Motel - Knowledge Base for Voice Agent
==================================================
This module provides searchable functions for the voice agent to lookup
specific motel information on-demand, keeping the base prompt lean.

Strategy: Agent calls these functions when user asks detailed questions,
giving a natural "let me check that for you" moment.
"""

from typing import Optional, Dict, List, Any

# =============================================================================
# ROOM INFORMATION DATABASE
# =============================================================================

ROOMS = {
    "queen": {
        "name": "Queen Room",
        "price": 130,
        "max_guests": 2,
        "bedding": "Queen Bed",
        "best_for": "Solo travellers, couples, business guests",
        "facilities": [
            "Queen Bed", "Table + chairs", "Couch", "Air-conditioner/heating",
            "HD flat screen TV", "En-suite bathroom", "Free WiFi",
            "Coffee/tea making facilities", "Toaster", "Microwave",
            "Bar fridge", "Oil heater", "Hairdryer", "Iron and ironing board",
            "At-door parking"
        ]
    },
    "twin": {
        "name": "Twin Room",
        "price": 140,
        "max_guests": 3,
        "bedding": "Queen Bed + Single Bed",
        "best_for": "Friends travelling together, small groups",
        "facilities": [
            "Queen Bed plus Single Bed", "Table + chairs", "Air-conditioner/heating",
            "HD flat screen TV", "En-suite bathroom", "Free WiFi",
            "Coffee/tea making facilities", "Toaster", "Microwave",
            "Bar fridge", "Oil heater", "Hairdryer", "Iron and ironing board",
            "At-door parking"
        ]
    },
    "family": {
        "name": "Family Room",
        "price": 160,
        "max_guests": 4,
        "bedding": "Queen Bed + Two Single Beds",
        "best_for": "Families, groups of friends",
        "facilities": [
            "Queen Bed plus Two Single Beds", "Air-conditioner/heating",
            "HD flat screen TV", "En-suite bathroom", "Free WiFi",
            "Coffee/tea making facilities", "Toaster", "Microwave",
            "Bar fridge", "Oil heater", "Hairdryer", "Iron and ironing board",
            "At-door parking"
        ]
    },
    "accessible": {
        "name": "Accessible Room",
        "price": 130,
        "max_guests": 3,
        "bedding": "Queen Bed + Single Bed",
        "best_for": "Guests with reduced mobility",
        "special_features": [
            "Flat floor internally",
            "Open shower with hand rails and shower stool",
            "Note: NOT adjusted for all special needs - contact to discuss requirements"
        ],
        "facilities": [
            "Queen Bed plus Single Bed", "Open Shower with hand rails and stool",
            "Table + chairs", "Air-conditioner/heating", "HD flat screen TV",
            "En-suite bathroom", "Free WiFi", "Coffee/tea making facilities",
            "Toaster", "Microwave", "Bar fridge", "Oil heater", "Hairdryer",
            "Iron and ironing board", "At-door parking"
        ]
    }
}

# =============================================================================
# MOTEL GENERAL INFO
# =============================================================================

MOTEL_INFO = {
    "name": "The Lydoun Motel Chiltern",
    "address": "7 Main Street, Chiltern Vic 3683, Australia",
    "phone": "(03) 5726 1788",
    "total_rooms": 14,
    "reception_hours": "7:30am – 9:00pm",
    "check_in": "From 2:00pm",
    "check_out": "Prior to 10:00am",
    "owner": "Meena",
    "established_rebrand": 2017,
    "previous_name": "The Chiltern Colonial Motor Inn"
}

AMENITIES = [
    "All Rooms at Ground Level",
    "Reduced Mobility Room available",
    "100% Non Smoking Rooms",
    "Complimentary WiFi",
    "Room Service",
    "Extra Single Bed or Cot Available",
    "Seasonal Pool",
    "Guest BBQ",
    "Free Onsite Parking",
    "Guest Laundry Facilities",
    "Large Vehicle Parking Area",
    "Group Bookings (contact directly)"
]

LOCATION_INFO = {
    "description": "Just off the Hume Freeway, midway between Wangaratta and Wodonga",
    "region": "North East Victoria",
    "national_park": "Chiltern Mt Pilot National Park",
    "distances": {
        "Melbourne": "3 hours north",
        "Canberra": "4 hours south",
        "Albury/Wodonga": "30 minutes",
        "Wangaratta": "30 minutes",
        "Rutherglen wine region": "20 minutes north",
        "Beechworth": "20 minutes south",
        "Yackandandah": "20 minutes east",
        "Albury Regional Airport": "30 minutes drive"
    },
    "travel_options": {
        "car": "Just off the Hume Freeway",
        "train": "Historic railway station on Melbourne-Sydney rail line",
        "plane": "30 minutes from Albury Regional Airport",
        "boat": "3 hours from Spirit of Tasmania dock (late check-in available)"
    }
}

ACTIVITIES = [
    "Gold fossicking",
    "Bird watching",
    "Cycling",
    "Walking trails",
    "Antique browsing",
    "Horse riding",
    "Fishing and hunting",
    "Photography",
    "Wine tasting (Rutherglen)",
    "Craft beer and spirits tasting"
]

# =============================================================================
# SEARCH FUNCTIONS (Used by Voice Agent via Function Calling)
# =============================================================================

def get_room_pricing(room_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get pricing information for rooms.
    
    Args:
        room_type: Optional - "queen", "twin", "family", "accessible", or None for all
    
    Returns:
        Pricing details with price per night and what's included
    """
    if room_type and room_type.lower() in ROOMS:
        room = ROOMS[room_type.lower()]
        return {
            "room_type": room["name"],
            "price_per_night": room["price"],
            "max_guests": room["max_guests"],
            "bedding": room["bedding"],
            "best_for": room["best_for"],
            "note": "Prices are starting from and may vary by date"
        }
    
    # Return all pricing
    return {
        "rooms": [
            {
                "type": key,
                "name": room["name"],
                "price": room["price"],
                "max_guests": room["max_guests"]
            }
            for key, room in ROOMS.items()
        ],
        "note": "All prices are 'from' rates per night"
    }


def get_room_details(room_type: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific room type.
    
    Args:
        room_type: "queen", "twin", "family", or "accessible"
    
    Returns:
        Full room details including all facilities
    """
    room_type = room_type.lower()
    if room_type not in ROOMS:
        return {
            "error": "Room type not found",
            "available_types": list(ROOMS.keys())
        }
    
    room = ROOMS[room_type]
    result = {
        "name": room["name"],
        "price_from": f"${room['price']}/night",
        "max_guests": room["max_guests"],
        "bedding": room["bedding"],
        "best_for": room["best_for"],
        "facilities": room["facilities"]
    }
    
    if "special_features" in room:
        result["special_features"] = room["special_features"]
    
    return result


def get_amenities(category: Optional[str] = None) -> Dict[str, Any]:
    """
    Get motel amenities information.
    
    Args:
        category: Optional filter - "parking", "accessibility", "wifi", etc.
    
    Returns:
        List of amenities, filtered if category provided
    """
    if category:
        category = category.lower()
        filtered = [a for a in AMENITIES if category in a.lower()]
        return {"amenities": filtered if filtered else AMENITIES}
    
    return {"amenities": AMENITIES}


def get_check_in_out_info() -> Dict[str, str]:
    """Get check-in and check-out times and policies."""
    return {
        "check_in": MOTEL_INFO["check_in"],
        "check_out": MOTEL_INFO["check_out"],
        "reception_hours": MOTEL_INFO["reception_hours"],
        "parking": "Free parking right outside your room",
        "late_check_in": "Available upon request - please call ahead"
    }


def get_location_info(detail: Optional[str] = None) -> Dict[str, Any]:
    """
    Get location and distance information.
    
    Args:
        detail: Optional - "distances", "travel", or None for overview
    
    Returns:
        Location details
    """
    if detail == "distances":
        return {"distances": LOCATION_INFO["distances"]}
    elif detail == "travel":
        return {"travel_options": LOCATION_INFO["travel_options"]}
    
    return {
        "address": MOTEL_INFO["address"],
        "description": LOCATION_INFO["description"],
        "region": LOCATION_INFO["region"],
        "national_park": LOCATION_INFO["national_park"]
    }


def get_activities_nearby() -> Dict[str, List[str]]:
    """Get list of activities and attractions nearby."""
    return {
        "activities": ACTIVITIES,
        "nearby_areas": [
            "King Valley", "Beechworth", "Rutherglen",
            "Eldorado", "Myrtleford", "Bright"
        ]
    }


def recommend_room(num_guests: int, needs_accessibility: bool = False) -> Dict[str, Any]:
    """
    Recommend the best room based on guest count and requirements.
    
    Args:
        num_guests: Number of guests
        needs_accessibility: Whether accessible features are needed
    
    Returns:
        Room recommendation with reasoning
    """
    if needs_accessibility:
        room = ROOMS["accessible"]
        return {
            "recommended": "Accessible Room",
            "price": room["price"],
            "reason": "Features flat floor, open shower with hand rails",
            "note": "Please call to discuss specific accessibility needs"
        }
    
    if num_guests == 1:
        return {
            "recommended": "Queen Room",
            "price": 130,
            "reason": "Perfect for solo travellers, best value"
        }
    elif num_guests == 2:
        return {
            "recommended": "Queen Room",
            "price": 130,
            "reason": "Comfortable queen bed for couples"
        }
    elif num_guests == 3:
        return {
            "recommended": "Twin Room",
            "price": 140,
            "reason": "Queen bed plus single bed, fits 3 comfortably"
        }
    else:  # 4+
        return {
            "recommended": "Family Room",
            "price": 160,
            "reason": "Queen bed plus two singles, perfect for families up to 4",
            "note": "For larger groups, please call to discuss options"
        }


def search_motel_info(query: str) -> Dict[str, Any]:
    """
    General search across all motel information.
    
    Args:
        query: Search term (e.g., "wifi", "pool", "parking", "pets")
    
    Returns:
        Relevant information matching the query
    """
    query = query.lower()
    results = {}
    
    # Search amenities
    matching_amenities = [a for a in AMENITIES if query in a.lower()]
    if matching_amenities:
        results["amenities"] = matching_amenities
    
    # Search room facilities
    for room_type, room in ROOMS.items():
        matching_facilities = [f for f in room["facilities"] if query in f.lower()]
        if matching_facilities:
            results[f"{room['name']}_facilities"] = matching_facilities
    
    # Search activities
    matching_activities = [a for a in ACTIVITIES if query in a.lower()]
    if matching_activities:
        results["activities"] = matching_activities
    
    # Common queries
    if "pet" in query or "dog" in query:
        results["pets"] = "Please call to discuss pet policy"
    
    if "smoke" in query or "smoking" in query:
        results["smoking"] = "100% Non Smoking Rooms"
    
    if "pool" in query or "swim" in query:
        results["pool"] = "Seasonal Pool available"
    
    if "wifi" in query or "internet" in query:
        results["wifi"] = "Complimentary WiFi in all rooms"
    
    if not results:
        results["note"] = f"No specific info found for '{query}'. Please ask reception."
    
    return results


async def lookup_booking(guest_name: str, phone: str = None, reference: str = None) -> Dict[str, Any]:
    """
    Look up an existing booking by guest name and optional verification.
    
    Uses fuzzy matching for names and normalizes phone numbers from speech.
    
    Args:
        guest_name: The guest's name (required) - can include titles like "mister"
        phone: Guest's phone number (optional) - can be spoken like "o four nine..."
        reference: Booking reference number (optional, for direct lookup)
    
    Returns:
        Booking details if found, or appropriate error message
    """
    import httpx
    import os
    
    # Import text utilities for normalization
    try:
        from services.voice_agent.text_utils import (
            normalize_phone_number,
            normalize_guest_name,
            fuzzy_name_match,
            is_valid_au_phone,
        )
    except ImportError:
        # Fallback to basic normalization if utils not available
        normalize_phone_number = lambda x: x.replace(" ", "")
        normalize_guest_name = lambda x: x.lower().strip()
        fuzzy_name_match = lambda a, b, t=0.6: normalize_guest_name(a) in normalize_guest_name(b) or normalize_guest_name(b) in normalize_guest_name(a)
        is_valid_au_phone = lambda x: (True, "")
    
    # Get Appwrite config from environment
    endpoint = os.getenv("APPWRITE_ENDPOINT")
    project_id = os.getenv("APPWRITE_PROJECT_ID")
    api_key = os.getenv("APPWRITE_API_KEY")
    motel_db_id = "6947b8300005f5863f96"
    
    headers = {
        "Content-Type": "application/json",
        "X-Appwrite-Project": project_id,
        "X-Appwrite-Key": api_key
    }
    
    # Normalize inputs
    search_name = normalize_guest_name(guest_name)
    search_phone = normalize_phone_number(phone) if phone else None
    
    # Log normalized values for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔍 Booking lookup: name='{guest_name}' -> '{search_name}', phone='{phone}' -> '{search_phone}'")
    
    # Validate phone format if provided
    if phone:
        is_valid, validation_msg = is_valid_au_phone(phone)
        if not is_valid:
            logger.info(f"⚠️ Invalid phone format: {validation_msg}")
            return {
                "found": False,
                "phone_invalid": True,
                "message": validation_msg
            }
    
    try:
        # Fetch reservations from Appwrite
        url = f"{endpoint}/databases/{motel_db_id}/collections/motel_reservations/documents"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            
            if response.status_code != 200:
                return {
                    "found": False,
                    "message": "I'm having trouble accessing the booking system right now. Please try again or contact reception at (03) 5726 1788."
                }
            
            data = response.json()
            documents = data.get("documents", [])
            
            # Log total documents for debugging
            logger.info(f"📊 Total reservations in database: {len(documents)}")
            
            # Two-pass search: First by name, then score by phone similarity
            name_matches = []
            
            for doc in documents:
                doc_name = doc.get("guest_name") or ""
                doc_phone = normalize_phone_number(doc.get("guest_phone") or "")
                doc_ref = doc.get("booking_reference", "")
                
                # Log each document being checked
                normalized_doc_name = normalize_guest_name(doc_name)
                logger.debug(f"   Checking: '{doc_name}' -> '{normalized_doc_name}', phone: '{doc_phone}'")
                
                # Direct reference match takes priority - return immediately
                if reference and doc_ref.upper() == reference.upper():
                    logger.info(f"✅ Found by reference: {doc_ref}")
                    return {
                        "found": True,
                        "booking": {
                            "guest_name": doc.get("guest_name"),
                            "room_type": doc.get("room_type", "").title(),
                            "check_in": doc.get("check_in_date"),
                            "check_out": doc.get("check_out_date"),
                            "num_guests": doc.get("num_guests"),
                            "total_amount": doc.get("total_amount"),
                            "status": doc.get("status", "pending"),
                            "reference": doc.get("booking_reference")
                        },
                        "message": f"Found your booking! Reference: {doc.get('booking_reference')}"
                    }
                
                # Fuzzy name matching
                if fuzzy_name_match(search_name, doc_name):
                    # Calculate phone similarity score
                    phone_score = 0
                    if search_phone and doc_phone:
                        # Check various matching criteria
                        if search_phone == doc_phone:
                            phone_score = 100  # Exact match
                        elif search_phone in doc_phone or doc_phone in search_phone:
                            phone_score = 80  # Substring match
                        elif len(search_phone) >= 6 and len(doc_phone) >= 6:
                            # Compare last 6 digits
                            if search_phone[-6:] == doc_phone[-6:]:
                                phone_score = 70
                            # Compare last 4 digits
                            elif search_phone[-4:] == doc_phone[-4:]:
                                phone_score = 50
                    
                    logger.info(f"✅ Name match: '{doc_name}' (phone score: {phone_score})")
                    name_matches.append({
                        "doc": doc,
                        "phone_score": phone_score
                    })
            
            # If no matches by name
            if not name_matches:
                normalized_display = search_name.title()
                logger.info(f"❌ No name matches found for '{normalized_display}'")
                return {
                    "found": False,
                    "searched_name": normalized_display,
                    "searched_phone": search_phone,
                    "message": f"I couldn't find a booking under the name '{normalized_display}'. Could you spell out your name for me, or provide a booking reference number?"
                }
            
            # Sort by phone score (best match first)
            name_matches.sort(key=lambda x: x["phone_score"], reverse=True)
            
            # If multiple name matches, use phone to pick best one
            if len(name_matches) > 1:
                best_match = name_matches[0]
                # If best match has significantly better phone score, use it
                if best_match["phone_score"] >= 50:
                    logger.info(f"📌 Selected best match by phone score: {best_match['phone_score']}")
                    booking = best_match["doc"]
                else:
                    # Can't determine which one - ask for clarification
                    return {
                        "found": True,
                        "multiple": True,
                        "count": len(name_matches),
                        "message": f"I found {len(name_matches)} bookings that might match. Could you provide your booking reference number to find the right one?"
                    }
            else:
                booking = name_matches[0]["doc"]
            return {
                "found": True,
                "booking": {
                    "guest_name": booking.get("guest_name"),
                    "room_type": booking.get("room_type", "").title(),
                    "check_in": booking.get("check_in_date"),
                    "check_out": booking.get("check_out_date"),
                    "num_guests": booking.get("num_guests"),
                    "total_amount": booking.get("total_amount"),
                    "status": booking.get("status", "pending"),
                    "reference": booking.get("booking_reference")
                },
                "message": f"Found your booking! Reference: {booking.get('booking_reference')}"
            }
            
    except Exception as e:
        logger.error(f"Booking lookup error: {e}")
        return {
            "found": False,
            "message": "I'm having trouble looking that up right now. Please contact reception at (03) 5726 1788 for booking inquiries."
        }


# =============================================================================
# FUNCTION DEFINITIONS FOR DEEPGRAM VOICE AGENT
# =============================================================================

def get_motel_search_functions() -> list:
    """
    Returns function definitions for Deepgram voice agent function calling.
    These are added to the agent's capabilities for on-demand lookups.
    """
    return [
        {
            "name": "get_room_pricing",
            "description": "Get room prices. Use when customer asks about rates, costs, or pricing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_type": {
                        "type": "string",
                        "description": "Room type: queen, twin, family, or accessible. Leave empty for all prices.",
                        "enum": ["queen", "twin", "family", "accessible"]
                    }
                }
            }
        },
        {
            "name": "get_room_details",
            "description": "Get detailed room information including all facilities. Use when customer asks what's in a room.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_type": {
                        "type": "string",
                        "description": "Room type: queen, twin, family, or accessible",
                        "enum": ["queen", "twin", "family", "accessible"]
                    }
                },
                "required": ["room_type"]
            }
        },
        {
            "name": "recommend_room",
            "description": "Get room recommendation based on number of guests and accessibility needs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "num_guests": {
                        "type": "integer",
                        "description": "Number of guests staying"
                    },
                    "needs_accessibility": {
                        "type": "boolean",
                        "description": "Whether accessible features are needed"
                    }
                },
                "required": ["num_guests"]
            }
        },
        {
            "name": "get_check_in_out_info",
            "description": "Get check-in and check-out times. Use when customer asks about arrival/departure times.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "get_location_info",
            "description": "Get location and distance information. Use when customer asks how to get here or how far.",
            "parameters": {
                "type": "object",
                "properties": {
                    "detail": {
                        "type": "string",
                        "description": "What info: 'distances' for how far things are, 'travel' for transport options",
                        "enum": ["distances", "travel"]
                    }
                }
            }
        },
        {
            "name": "get_amenities",
            "description": "Get motel amenities. Use when customer asks about facilities like pool, parking, wifi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional filter: parking, pool, wifi, laundry, etc."
                    }
                }
            }
        },
        {
            "name": "get_activities_nearby",
            "description": "Get nearby activities and attractions. Use when customer asks what there is to do.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "search_motel_info",
            "description": "General search for any motel information. Use as fallback for specific questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term like 'pets', 'smoking', 'breakfast', etc."
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "lookup_booking",
            "description": "Look up an existing booking when customer wants to check their reservation. Ask for their name first, then reference or phone if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_name": {
                        "type": "string",
                        "description": "The guest's name as it appears on the booking"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Guest's phone number for verification (optional)"
                    },
                    "reference": {
                        "type": "string",
                        "description": "Booking reference number like LYD-XXXXX (optional)"
                    }
                },
                "required": ["guest_name"]
            }
        }
    ]
