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
Returns a concise, token-efficient string of available rooms (e.g., 'Available: Queen, Twin. Unavailable: Family'). 
If availability cannot be verified, apologize briefly and transfer to staff (between 8:00 AM – 8:00 PM AEST and after confirming with user only).""",
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
            "description": """Create a booking and instantly send a payment link to the guest's email.

MANDATORY GATE — you MUST complete ALL 3 steps before calling this function:
  STEP 1: Collected first name + last name (confirmed spelling if unusual).
  STEP 2: Spelled out the email character by character AND received a verbal YES/confirmation.
  STEP 3: Read back the FULL one-line summary IN ONE SENTENCE and received a verbal YES:
    "Just to confirm — [First Name Last Name], checking in [spoken date], checking out [spoken date], [Room Type] at $[price] per night, total $[total]. That email is [spell email letter by letter]. Is all of that correct?"
    The STEP 3 summary MUST include: full name, check-in, check-out, room type, price per night, total, AND email.
    A "Yep" confirming only the email address is NOT sufficient — the full summary must be read and confirmed.

If ANY step is incomplete — DO NOT call this function. Complete the missing step first.
Set has_user_confirmed_summary="YES" ONLY after the caller said YES to the complete STEP 3 summary above.
If this tool fails validation, it will return a natural language error (e.g., 'Email invalid'). You MUST read this error, inform the user, and ask for the specific correction required.""",
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
                        "description": "Room type to book. CRITICAL MAPPING: 'double' or 'double room' ALWAYS maps to 'queen'. 'twin' is ONLY used when caller explicitly says 'twin' or 'two single beds'. Never use 'twin' for a 'double' request."
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
                        "description": "Guest email address for confirmation. REQUIRED — must be spelled and confirmed by caller first."
                    },
                    "notes": {
                        "type": "string",
                        "description": "Any special requests or notes"
                    },
                    "has_user_confirmed_summary": {
                        "type": "string",
                        "description": "CRITICAL STATE FLAG: You MUST pass the string 'YES' here if the caller has explicitly said 'YES' (or agreed) after you read back the full booking summary. Pass the string 'NO' if they haven't confirmed it yet. If you omit this or pass 'NO', the booking will instantly fail. Do not drop this flag."
                    }
                },
                "required": ["guest_name", "check_in_date", "room_type", "guest_email", "has_user_confirmed_summary"]
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
            "description": """Look up an existing booking. Call this as soon as the guest mentions their name or booking reference. The system auto-uses the caller's Twilio number; DO NOT ask for phone number first. 
If found=true, use the surfaced semantic booking details (e.g., semantic booking_id like CC-123, NOT uuids) to confirm naturally. 
If found_by=caller_phone is returned, confirm the likely booking instead of asking for brittle identifiers. 
Only pass email or reference if a previous call returned found=false.
Return Schema: This tool returns concise, high-signal context (status, dates, semantic IDs).""",
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
            "description": """Resend the booking confirmation receipt email. 

MANDATORY PRE-CHECK: You MUST call lookup_booking BEFORE calling this tool.
Only call this if lookup_booking returned payment_confirmed=true (payment_status='paid').
If payment_confirmed=false, the backend will reject the call anyway — but you must check first so you can tell the user the correct status before wasting a round-trip.

Do NOT call this tool if:
- The caller just said 'send me a confirmation' without you having checked their payment status
- lookup_booking returned payment_status != 'paid'
- You just created the booking (payment is always pending at creation time)""",
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
            "name": "resend_payment_link",
            "description": "Resend the payment link email. ONLY use this when the user has an unpaid or pending booking and explicitly says they haven't received the payment link, or they ask you to send it again.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_email": {
                        "type": "string",
                        "description": "Guest email address to send the payment link to"
                    }
                },
                "required": ["guest_email"]
            }
        },
        {
            "name": "request_human_callback",
            "description": "Request staff callback for complex issues or group bookings. MANDATORY GATE: You MUST ask the customer for their name before invoking this tool if it is not already in memory (e.g., 'Sure, could I please get your name so I can arrange that callback?'). Do NOT invent placeholders or generic names. Only call this tool after receiving their name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The customer's name (MUST ask the caller for this first if not already known)"
                    },
                    "customer_phone": {
                        "type": "string",
                        "description": "The customer's phone number for callback"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for callback"
                    },
                    "urgency": {
                        "type": "string", 
                        "enum": ["low", "medium", "high"],
                        "description": "Urgency level"
                    }
                },
                "required": ["reason"]
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
            "description": """CRITICAL: Call this function IMMEDIATELY if the user uses WAIT SIGNALS (e.g., 'give me a sec', 'hold on', 'one moment', 'wait a minute', 'wait a while', 'let me check', 'I'll do that', 'let me pay', 'processing it', 'bear with me'). 
Starts passive wait mode. Say ONE word ('Sure.' or 'Of course.') and call this tool. No questions, no continuation.""",
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
            "description": "Transfer the caller to a staff member or receptionist. ONLY use when the caller explicitly says YES to a transfer offer, or explicitly asks to be transferred (e.g., 'speak to someone', 'transfer me'). NEVER execute this proactively without explicit permission. If the user interrupts you or does not give clear confirmation, DO NOT transfer them. CRITICAL: If you just attempted a transfer and NO ONE ANSWERED (you are in the fallback flow), DO NOT call this again in the same turn.",
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
            "name": "hang_up_call",
            "description": "End the call and gracefully disconnect the phone line. ONLY use this when the caller explicitly says goodbye, bye, or indicates they are completely finished and no longer need assistance. Do NOT use this if the caller is just pausing or if you are transferring them.",
            "parameters": {
                "type": "object",
                "properties": {
                    "farewell_message": {
                        "type": "string",
                        "description": "A short, polite goodbye message to say before hanging up (e.g. 'Thanks for calling, goodbye.')."
                    }
                }
            }
        }
    ]
