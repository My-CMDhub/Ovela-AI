"""
Voice Agent Function Definitions Module.

Contains OpenAI-compatible function definitions for the Deepgram Voice Agent.
These are the tools the agent can call during conversations.

Function definitions are here, implementations are in handlers.py.
"""

from .handlers import FunctionDispatcher
from .saranda_handlers import SarandaFunctionDispatcher
from .saranda_definitions import get_saranda_functions

__all__ = ['get_booking_functions', 'FunctionDispatcher', 'SarandaFunctionDispatcher', 'get_saranda_functions']


def get_booking_functions() -> list:
    """
    Returns list of function definitions for the agent to use.
    
    These follow OpenAI function calling format.
    """
    return [
        {
            "name": "check_availability",
            "description": "Check if a room type is available for specific dates. Use when guest asks about availability.",
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
                        "enum": ["queen", "twin", "family", "accessible"],
                        "description": "Room type to check availability for"
                    }
                },
                "required": ["check_in_date"]
            }
        },
        {
            "name": "create_booking",
            "description": "Create a provisional room booking for a guest. Use after confirming their dates and collecting their name.",
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
                        "enum": ["queen", "twin", "family", "accessible"],
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
                    "notes": {
                        "type": "string",
                        "description": "Any special requests or notes"
                    },
                    "guest_email": {
                        "type": "string",
                        "description": "Guest email address for booking confirmation (optional)"
                    }
                },
                "required": ["guest_name", "check_in_date", "room_type"]
            }
        },
        {
            "name": "get_room_pricing",
            "description": "Get ONLY the price for a specific room type. Only use this when the guest specifically asks for pricing/rates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_type": {
                        "type": "string",
                        "enum": ["queen", "twin", "family", "accessible"],
                        "description": "Room type to get pricing for"
                    }
                },
                "required": ["room_type"]
            }
        },
        {
            "name": "get_room_details",
            "description": "Get full details about a room type including amenities, beds, and features. Use when guest wants to know more about what's in a room.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_type": {
                        "type": "string",
                        "enum": ["queen", "twin", "family", "accessible"],
                        "description": "Room type to get details for"
                    }
                },
                "required": ["room_type"]
            }
        },
        {
            "name": "recommend_room",
            "description": "Recommend the best room based on guest's needs (number of guests, special needs, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "num_guests": {
                        "type": "integer",
                        "description": "Number of guests"
                    },
                    "needs_accessibility": {
                        "type": "boolean",
                        "description": "Whether guest has mobility needs"
                    },
                    "prefer_separate_beds": {
                        "type": "boolean",
                        "description": "If 2 guests prefer separate beds"
                    }
                },
                "required": ["num_guests"]
            }
        },
        {
            "name": "get_check_in_out_info",
            "description": "Get check-in and check-out times. Use when guest asks about timing.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "get_location_info",
            "description": "Get motel location, directions, and contact info.",
            "parameters": {
                "type": "object", 
                "properties": {}
            }
        },
        {
            "name": "get_amenities",
            "description": "Get info about specific motel amenities like pool, WiFi, parking, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amenity": {
                        "type": "string",
                        "description": "Specific amenity to ask about (pool, wifi, parking, bbq, laundry, etc)"
                    }
                },
                "required": ["amenity"]
            }
        },
        {
            "name": "get_activities_nearby",
            "description": "Get information about things to do in the Chiltern area.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "search_motel_info",
            "description": "General search for any motel information. Use as fallback for specific questions about pets, smoking, breakfast, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term like 'pets', 'smoking', 'breakfast', 'cot', etc."
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "lookup_booking",
            "description": "Look up an existing booking for a guest. Use when guest wants to check or confirm their reservation. Ask for their name first.",
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
                        "description": "Booking reference number like LM-XXXXX (optional)"
                    }
                },
                "required": ["guest_name"]
            }
        },
        {
            "name": "flag_off_topic",
            "description": "IMPORTANT: Call this when a caller is wasting time with off-topic behavior. Examples: flirting, personal questions about you, repeated nonsense, tangential 'why' chains, demands for info you can't provide. Call this EACH TIME they do something off-topic - the system tracks the count and will tell you how to respond.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief description of why this is off-topic (e.g., 'flirting', 'personal questions', 'repeated nonsense', 'demanding other guest info')"
                    }
                },
                "required": ["reason"]
            }
        },
        {
            "name": "update_guest_info",
            "description": "Save guest details (name, phone) to memory. Call this IMMEDIATELY after a guest provides or confirms their name/contact info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_name": {
                        "type": "string",
                        "description": "The guest's full name"
                    },
                    "guest_phone": {
                        "type": "string",
                        "description": "The guest's phone number"
                    },
                    "guest_email": {
                        "type": "string",
                        "description": "The guest's email address (optional)"
                    }
                },
                "required": ["guest_name"]
            }
        },
        {
            "name": "request_human_callback",
            "description": "Request a human staff member to call the customer back. Use this when: (1) caller asks to speak to a human/manager, (2) you cannot answer their question (e.g., cancellation policies, refunds, complaints), (3) caller seems frustrated. Collects their name and phone, then notifies reception.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The customer's name"
                    },
                    "customer_phone": {
                        "type": "string",
                        "description": "The customer's phone number for callback"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for callback (e.g., 'refund inquiry', 'cancellation policy', 'complaint')"
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "How urgent is this callback request"
                    }
                },
                "required": ["customer_name", "customer_phone", "reason"]
            }
        },
        {
            "name": "report_missing_booking",
            "description": "Report a missing booking to staff. Use ONLY when: (1) You looked up a booking and found nothing, AND (2) The user claims they booked via 'Walk-in' (desk) or 'Website' (online) or 'Third Party'. Collect their details so staff can investigate manual records.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_name": {"type": "string", "description": "Guest name"},
                    "booking_source": {"type": "string", "enum": ["walk_in", "website", "ota", "other"], "description": "How they say they booked"},
                    "expected_check_in": {"type": "string", "description": "Expected check-in date (optional)"},
                    "contact_phone": {"type": "string", "description": "Phone number to reach them back"}
                },
                "required": ["guest_name", "booking_source"]
            }
        },
        {
            "name": "transfer_to_staff",
            "description": "Transfer the call to a staff member. Use IMMEDIATELY when caller says 'transfer me', 'talk to a person', 'speak to staff', 'speak to someone', 'human please', 'real person'. No arguments needed. No persuasion. Just transfer.",
            "parameters": {
                "type": "object",
                "properties": {}
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
        },
        {
            "name": "end_call",
            "description": "End the call gracefully. optionally provide a 'message' to speak before hanging up. Use when: (1) Leaving a voicemail (provide the message!), (2) Customer confirms they're done, (3) Conversation ends.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Optional message to speak before hanging up. critically useful for leaving voicemails. If provided, the agent will speak this text then hang up."
                    }
                }
            }
        }
    ]
