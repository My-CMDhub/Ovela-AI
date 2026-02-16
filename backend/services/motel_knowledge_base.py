"""
Coal Creek Motel - Knowledge Base
=================================
This module provides searchable functions for the voice agent to lookup
specific motel information on-demand.
"""

from typing import Optional, Dict, List, Any
from .knowledge_base.data_types import MotelData
from .knowledge_base.coalcreek import COALCREEK_DATA
from contextvars import ContextVar
import httpx
import os


# Global context to store current tenant for the request scope
# In a full async server, this should be a context var, but for this handler pattern
# we will rely on the function arguments or a simple set/get pattern if singular.
# Ideally, the functions themselves should accept tenant_id, but the OpenAI tools 
# schema is fixed. We'll use a ContextVar for thread-safety.



_current_tenant: ContextVar[str] = ContextVar("current_tenant", default="coalcreek")

def set_tenant_context(tenant_id: str):
    """Set the active tenant for the current request context."""
    _current_tenant.set(tenant_id)

def get_active_data() -> MotelData:
    """Get the knowledge base data for the active tenant."""
    # Currently defaults to Coal Creek Motel data
    return COALCREEK_DATA

# =============================================================================
# SEARCH FUNCTIONS (Used by Voice Agent via Function Calling)
# =============================================================================

def get_room_pricing(room_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get pricing information for rooms.
    
    Args:
        room_type: Optional - specific room type key or None for all
    
    Returns:
        Pricing details with price per night and what's included
    """
    data = get_active_data()
    rooms = data["rooms"]
    
    if room_type:
        room_type = room_type.lower().replace(" ", "_") # creative normalization
        # Try exact match first
        if room_type in rooms:
            room = rooms[room_type]
            return {
                "room_type": room["name"],
                "price_per_night": room["price"],
                "max_guests": room["max_guests"],
                "bedding": room["bedding"],
                "best_for": room["best_for"],
                "note": "Prices are starting from and may vary by date"
            }
        
        # Try partial match if no exact match (e.g. "queen" matches "deluxe_queen")
        for key, room in rooms.items():
            if room_type in key or key in room_type:
                return {
                    "room_type": room["name"],
                    "price_per_night": room["price"],
                    "max_guests": room["max_guests"],
                    "bedding": room["bedding"],
                    "best_for": room["best_for"],
                    "note": f"Found matching room: {room['name']}"
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
            for key, room in rooms.items()
        ],
        "note": "All prices are 'from' rates per night"
    }


def get_room_details(room_type: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific room type.
    
    Args:
        room_type: specific room key
    
    Returns:
        Full room details including all facilities
    """
    data = get_active_data()
    rooms = data["rooms"]
    room_type_key = room_type.lower().replace(" ", "_")
    
    # Direct lookup
    if room_type_key in rooms:
        room = rooms[room_type_key]
    else:
        # Fuzzy lookup
        found = False
        for key, r in rooms.items():
            if room_type_key in key or key in room_type_key:
                room = r
                found = True
                break
        
        if not found:
            return {
                "error": f"Room type '{room_type}' not found",
                "available_types": list(rooms.keys())
            }
    
    result = {
        "name": room["name"],
        "price_from": f"${room['price']}/night",
        "max_guests": room["max_guests"],
        "bedding": room["bedding"],
        "best_for": room["best_for"],
        "facilities": room.get("facilities", []) or [f.strip() for f in room.get("features", "").split(",") if f.strip()]
    }
    
    if "special_features" in room and room["special_features"]:
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
    data = get_active_data()
    amenities_list = data["amenities"]
    
    if category:
        category = category.lower()
        filtered = [a for a in amenities_list if category in a.lower()]
        return {"amenities": filtered if filtered else amenities_list}
    
    return {"amenities": amenities_list}


def get_check_in_out_info() -> Dict[str, str]:
    """Get check-in and check-out times and policies."""
    data = get_active_data()
    info = data["info"]
    
    return {
        "check_in": info["check_in"],
        "check_out": info["check_out"],
        "reception_hours": info["reception_hours"],
        "parking": "Free parking available on-site",
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
    data = get_active_data()
    loc = data["location"]
    info = data["info"]
    
    if detail == "distances":
        return {"distances": loc["distances"]}
    elif detail == "travel":
        return {"travel_options": loc["travel_options"]}
    
    return {
        "address": info["address"],
        "description": loc["description"],
        "region": loc["region"],
        "national_park": loc["national_park"]
    }


def get_activities_nearby() -> Dict[str, List[str]]:
    """Get list of activities and attractions nearby."""
    data = get_active_data()
    location = data.get("location", {})
    
    # Extract nearby areas from location distances
    nearby_areas = []
    if "distances" in location:
        nearby_areas = list(location["distances"].keys())
    
    
    # Safely get activities or fallback to attractions
    activities = data.get("activities", [])
    if not activities and "location" in data and "nearby_attractions" in data["location"]:
        activities = data["location"]["nearby_attractions"]

    return {
        "activities": activities,
        "nearby_areas": nearby_areas,
        "region": location.get("region", "the area")
    }


def get_policies(policy_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get hotel policies (cancellation, payment).
    
    Args:
        policy_type: "cancellation", "payment", or None for all
    
    Returns:
        Policy details
    """
    data = get_active_data()
    policies = data["policies"]
    
    if policy_type:
        policy_type = policy_type.lower()
        if "cancel" in policy_type:
            return {"cancellation_policy": policies["cancellation"]}
        if "pay" in policy_type:
            return {"payment_policy": policies["payment"]}
    
    return {"policies": policies}


def recommend_room(num_guests: int, needs_accessibility: bool = False) -> Dict[str, Any]:
    """
    Recommend the best room based on guest count and requirements.
    """
    data = get_active_data()
    rooms = data["rooms"]
    
    # Paddle Steamer Logic (has more diverse room types)
    if needs_accessibility:
        # Check if accessible room exists
        if "accessible" in rooms:
            r = rooms["accessible"]
            return {"recommended": r["name"], "price": r["price"], "reason": r["best_for"]}
        elif "deluxe_king" in rooms: # Fallback implies ground floor
             r = rooms["deluxe_king"]
             return {"recommended": r["name"], "price": r["price"], "reason": "Ground floor access, spacious"}
    
    # General logic based on capacity
    best_fit = None
    min_price = 9999
    
    for key, r in rooms.items():
        if r["max_guests"] >= num_guests:
            # Find cheapest room that fits
            if r["price"] < min_price:
                min_price = r["price"]
                best_fit = r
            # Prefer 'family' room for 4+ guests even if price is higher
            if num_guests >= 4 and "family" in key:
                best_fit = r
                break
    
    if best_fit:
        return {
            "recommended": best_fit["name"],
            "price": best_fit["price"],
            "reason": f"Fits {num_guests} comfortably. {best_fit['best_for']}"
        }
        
    return {
        "recommended": "Multiple Rooms",
        "reason": "No single room fits that many guests. We recommend booking multiple rooms.",
        "note": "Please call reception to arrange a group booking."
    }


def search_motel_info(query: str) -> Dict[str, Any]:
    """
    General search across all motel information.
    """
    data = get_active_data()
    query = query.lower()
    results = {}
    
    # Search amenities
    matching_amenities = [a for a in data["amenities"] if query in a.lower()]
    if matching_amenities:
        results["amenities"] = matching_amenities
    
    # Search room facilities
    for key, room in data["rooms"].items():
        # Handle list or string features
        facilities = room.get("facilities", [])
        if not facilities and "features" in room:
             facilities = [f.strip() for f in room["features"].split(",") if f.strip()]
             
        matching_facilities = [f for f in facilities if query in f.lower()]
        if matching_facilities:
            results[f"{room['name']}_facilities"] = matching_facilities
    
    # Search activities (Safe Access)
    activities_list = data.get("activities", [])
    if not activities_list and "location" in data and "nearby_attractions" in data["location"]:
        activities_list = data["location"]["nearby_attractions"]

    matching_activities = [a for a in activities_list if query in a.lower()]
    if matching_activities:
        results["activities"] = matching_activities
    
    # Common queries logic
    if "pet" in query or "dog" in query:
        results["pets"] = "Please call to discuss pet policy"
    
    if "smoke" in query or "smoking" in query:
        results["smoking"] = "100% Non Smoking Rooms"
    
    if "pool" in query or "swim" in query:
        results["pool"] = "Pool information available in amenities"
    
    if "wifi" in query or "internet" in query:
        results["wifi"] = "Complimentary WiFi available"
        
    # Restaurant check (Critical for Paddle Steamer)
    if "restaurant" in query or "food" in query or "dinner" in query or "breakfast" in query:
        if "restaurant" in str(data).lower() and "closed" in str(data).lower():
             results["dining"] = "The restaurant is currently CLOSED. No breakfast or dinner service."
    
    if not results:
        results["note"] = f"No specific info found for '{query}'. Please ask reception."
    
    return results


async def lookup_booking(guest_name: str, phone: str = None, reference: str = None) -> Dict[str, Any]:
    """
    Look up an existing booking in the Coal Creek database.
    """
    tenant = _current_tenant.get()
    
    # Coal Creek: Use live database lookup
    if tenant == "coalcreek":
        # For now, return a message indicating we'll check manually
        # In production, this would query the motel_reservations collection
        return {
            "found": False,
            "message": f"I don't have access to the main booking calendar right now. If you have a confirmation email, I can forward your details to reception to double-check?"
        }
    
 
    
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
    
    try:
        # Fetch reservations from Appwrite
        url = f"{endpoint}/databases/{motel_db_id}/collections/motel_reservations/documents"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            
            if response.status_code != 200:
                return {
                    "found": False,
                    "message": "I'm having trouble accessing the booking system right now."
                }
            
            data = response.json()
            documents = data.get("documents", [])
            
            # Simple linear search logic (condensed)
            for doc in documents:
                 if fuzzy_name_match(search_name, doc.get("guest_name", "")):
                     return {
                        "found": True,
                        "booking": {
                            "guest_name": doc.get("guest_name"),
                            "room_type": doc.get("room_type", "").title(),
                            "check_in": doc.get("check_in_date"),
                            "reference": doc.get("booking_reference")
                        },
                        "message": f"Found your booking! Reference: {doc.get('booking_reference')}"
                    }
            
            return {
                "found": False,
                "message": f"I couldn't find a booking under the name '{guest_name}'."
            }
            
    except Exception as e:
        return {
            "found": False,
            "message": "System error on lookup."
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
                        "description": "Room type (e.g., queen, family). Leave empty for all.",
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
                        "description": "Room type key",
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
                        "description": "Booking reference number (optional)"
                    }
                },
                "required": ["guest_name"]
            }
        },
        {
            "name": "get_policies",
            "description": "Get cancellation or payment policies. Use when customer asks about refunds, fees, or how to pay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_type": {
                        "type": "string",
                        "description": "Type of policy: 'cancellation' or 'payment'. Leave empty for general policy info.",
                        "enum": ["cancellation", "payment"]
                    }
                }
            }
        }
    ]
