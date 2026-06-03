"""
Coal Creek Motel Function Definitions
=====================================
OpenAI-compatible function definitions for the Deepgram Voice Agent.
Specific to Coal Creek Motel's "Live Availability + Soft Hold" booking strategy.
"""

def get_coalcreek_functions() -> list:
    """
    Returns list of function definitions for Coal Creek Motel.
    
    Strategy:
    1. LIVE Availability: AI checks the live calendar via website scraping.
    2. SOFT HOLD Booking: AI creates a request, sends to staff, tells user "temporary hold".
    """
    return [
        # =================================================================
        # BOOKING OPERATIONS (Live Availability + Soft Hold)
        # =================================================================
        {
            "name": "check_availability",
            "description": """Check live room availability for Coal Creek Motel.

SPEAKING RULE: Say ONE of these:
  - "One moment , let me check..."
  - "Let me check that for you."
  - "Just a second, I'll look that up."
CRITICAL: If user asks "what's available?" or "other options" → use room_type='any' to check ALL rooms in ONE call. NEVER call this multiple times for different room types.

Multi-night stays validate EACH night. May take 3-10 seconds.
If availability cannot be verified, apologize briefly and transfer to staff.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "check_in_date": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format"
                    },
                    "check_out_date": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format (if not provided, assumes 1-night stay)"
                    },
                    "room_type": {
                        "type": "string",
                        "enum": ["queen", "twin", "family", "suite", "any"],
                        "description": "Specific room type to check, or 'any' for all rooms (HIGHLY RECOMMENDED)"
                    }
                },
                "required": ["check_in_date"]
            }
        },
        {
            "name": "create_booking_request",
            "description": "Create a booking and instantly send a payment link to the guest's email. DO NOT CALL THIS unless the caller has explicitly confirmed their email spelling.",
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
            "description": "Get price for a specific room type.",
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
            "description": "Look up an existing booking. Call this as soon as the guest mentions their name or booking reference — DON'T ask for phone number first, the system auto-uses the caller's Twilio number. If the result returns found=true, use the surfaced booking details to confirm naturally like a receptionist. If found_by=caller_phone is returned, confirm the likely booking instead of asking for brittle identifiers. Only pass email or reference if a previous call returned found=false.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_name": {"type": "string", "description": "Guest name as spoken — pass whatever the user said, system does fuzzy matching"},
                    "phone": {"type": "string", "description": "Only provide if guest explicitly gives a DIFFERENT phone number. Leave empty to auto-use caller's number."},
                    "email": {"type": "string", "description": "Only provide if previous lookup returned found=false"},
                    "reference": {"type": "string", "description": "Booking reference as spoken (e.g. 'CC 7 6 8 1 8') — system normalizes format automatically"}
                },
                "required": []
            }
        },
        {
            "name": "update_guest_info",
            "description": "Save guest info. CRITICAL: If fixing a wrong email, this function AUTOMATICALLY RESENDS the payment link. DO NOT call create_booking_request again after using this.",
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
            "name": "resend_payment_confirmation",
            "description": "Resend the payment confirmation or receipt email. ONLY use this when the user says they have already paid/secured the booking but didn't receive the payment receipt or confirmation email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_email": {
                        "type": "string",
                        "description": "Guest email address to send the receipt to"
                    }
                },
                "required": ["guest_email"]
            }
        },
        {
            "name": "request_human_callback",
            "description": "Request staff callback for complex issues or group bookings.",
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
            "name": "wait_on_request",
            "description": "CRITICAL: Call this function IMMEDIATELY if the user says 'give me a sec', 'hold on', 'one moment', 'wait a minute', 'wait a while', 'let me check', or asks you to wait or hold for any reason. Starts passive wait mode.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Short reason for waiting, if caller provided one (e.g., 'checking dates', 'grabbing card')."
                    },
                    "wait_seconds": {
                        "type": "integer",
                        "description": "Optional desired wait length in seconds. Default to 120 for 'wait a while', 90 for 'give me a sec'."
                    }
                }
            }
        },
        {
            "name": "transfer_to_staff",
            "description": "Transfer the caller to a staff member or receptionist. ONLY use when the caller explicitly says YES to a transfer offer, or explicitly asks to be transferred (e.g., 'speak to someone', 'transfer me'). NEVER execute this proactively without explicit permission. If the user interrupts you or does not give clear confirmation, DO NOT transfer them.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "perform_live_search",
            "description": "Perform a live Google Search for current, real-time information. Use immediately when a caller asks about: weather, temperature, rain, forecast, traffic, road conditions, local events, or any fact you cannot answer from memory. Do NOT ask the caller to confirm before searching — just search. NEVER use for general motel questions you can answer directly, playing music, or unrelated topics. only perform live search for what make sense actually during their trip for coalcreek area and chiltern ",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific and location-aware, e.g. 'current weather Chiltern Victoria Australia'."
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "end_call",
            "description": "End the call by saying goodbye. ONLY use when the caller explicitly wants to finish the conversation, such as 'bye', 'goodbye', 'see you', 'that's all', or when they clearly confirm they are done after your final help-offer. If they only say thanks, appreciation, or a polite wrap-up, do ONE final natural help-offer first instead of ending immediately. NEVER use this when they want to speak to staff or be transferred.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "confidence_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Your confidence level that the user genuinely wants to end the call right now."
                    }
                }
            }
        }
    ]
