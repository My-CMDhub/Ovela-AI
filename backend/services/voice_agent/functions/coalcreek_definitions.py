"""
Coal Creek Motel Function Definitions
=====================================
OpenAI-compatible function definitions for the Deepgram Voice Agent.
Specific to Coal Creek Motel's "Read-Only + Soft Hold" booking strategy.
"""

def get_coalcreek_functions() -> list:
    """
    Returns list of function definitions for Coal Creek Motel.
    
    Strategy:
    1. READ-ONLY Availability: AI checks if room is available but promises nothing.
    2. SOFT HOLD Booking: AI creates a request, sends to staff, tells user "temporary hold".
    """
    return [
        # =================================================================
        # BOOKING OPERATIONS (Read-Only + Soft Hold)
        # =================================================================
        {
            "name": "check_availability",
            "description": "Check if a room type is available for specific dates. READ-ONLY operation. Does NOT hold the room. Use this first when guest asks about dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "check_in_date": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format"
                    },
                    "check_out_date": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format (optional, defaults to next day)"
                    },
                    "room_type": {
                        "type": "string",
                        "enum": ["queen", "twin", "family", "suite"],
                        "description": "Room type to check (Standard Queen, Twin, Family, Deluxe Spa Suite)"
                    }
                },
                "required": ["check_in_date"]
            }
        },
        {
            "name": "create_booking_request",
            "description": "Create a provisional SOFT HOLD booking request. AI CANNOT CONFIRM booking instantly. Use this to place a hold and send to staff for approval. Tell guest: 'I've placed a temporary hold...'",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_name": {
                        "type": "string",
                        "description": "The guest's full name"
                    },
                    "check_in_date": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format"
                    },
                    "check_out_date": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format"
                    },
                    "room_type": {
                        "type": "string",
                        "enum": ["queen", "twin", "family", "suite"],
                        "description": "Room type to book"
                    },
                    "num_guests": {
                        "type": "integer",
                        "description": "Number of guests staying"
                    },
                    "guest_phone": {
                        "type": "string",
                        "description": "Guest phone number for confirmation"
                    },
                    "guest_email": {
                        "type": "string",
                        "description": "Guest email address for confirmation (optional)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Any special requests or notes"
                    }
                },
                "required": ["guest_name", "check_in_date", "room_type"]
            }
        },
        
        # =================================================================
        # PRICING & INFO
        # =================================================================
        {
            "name": "get_room_pricing",
            "description": "Get ONLY the price for a specific room type. Use when guest specifically asks for rates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_type": {
                        "type": "string",
                        "enum": ["queen", "twin", "family", "suite"],
                        "description": "Room type to get pricing for"
                    }
                },
                "required": ["room_type"]
            }
        },
        {
            "name": "get_room_details",
            "description": "Get full details about a room type (beds, amenities).",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_type": {
                        "type": "string",
                        "enum": ["queen", "twin", "family", "suite"],
                        "description": "Room type to get details for"
                    }
                },
                "required": ["room_type"]
            }
        },
        
        # =================================================================
        # GENERAL MOTEL INFO
        # =================================================================
        {
            "name": "get_check_in_out_info",
            "description": "Get check-in (2pm-8pm) and check-out (10am) times.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "get_location_info",
            "description": "Get location, directions (Korumburra), and nearby info.",
            "parameters": {
                "type": "object", 
                "properties": {}
            }
        },
        {
            "name": "get_amenities",
            "description": "Get info about amenities (parking, wifi, BBQ, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "amenity": {
                        "type": "string",
                        "description": "Specific amenity (pool, wifi, parking, bbq, etc)"
                    }
                },
                "required": ["amenity"]
            }
        },
        {
            "name": "get_activities_nearby",
            "description": "Get information about things to do in Korumburra/Coal Creek area.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        
        # =================================================================
        # POLICIES
        # =================================================================
        {
            "name": "get_policies",
            "description": "Get cancellation or payment policies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_type": {
                        "type": "string",
                        "description": "Type of policy: 'cancellation' or 'payment'",
                        "enum": ["cancellation", "payment"]
                    }
                }
            }
        },
        
        # =================================================================
        # ADMIN / UTILS
        # =================================================================
        {
            "name": "lookup_booking",
            "description": "Look up an existing booking. Ask for name first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_name": {"type": "string", "description": "Guest name"},
                    "phone": {"type": "string", "description": "Guest phone (optional)"},
                    "reference": {"type": "string", "description": "Booking reference (optional)"}
                },
                "required": ["guest_name"]
            }
        },
        {
            "name": "update_guest_info",
            "description": "Save guest name/phone/email to memory context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_name": {"type": "string"},
                    "guest_phone": {"type": "string"},
                    "guest_email": {"type": "string"}
                },
                "required": ["guest_name"]
            }
        },
        {
            "name": "request_human_callback",
            "description": "Request staff callback for complex issues, complaints, or group bookings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                    "customer_phone": {"type": "string"},
                    "reason": {"type": "string"},
                    "urgency": {"type": "string", "enum": ["low", "medium", "high"]}
                },
                "required": ["customer_name", "customer_phone", "reason"]
            }
        },
        {
            "name": "flag_off_topic",
            "description": "Flag off-topic behavior (flirting, nonsense).",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"}
                },
                "required": ["reason"]
            }
        },
        {
            "name": "transfer_to_staff",
            "description": "Transfer call to staff immediately when requested.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "end_call",
            "description": "End the call gracefully.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                }
            }
        }
    ]
