"""
AI Tool Definitions
OpenAI function calling tool schemas for the booking system.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment slots for a specific date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string", 
                        "description": "Date in YYYY-MM-DD format. Example: 2025-12-15"
                    }
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_booking_request",
            "description": "Submit a booking request for owner approval. Collects name, optional email, service, date and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "Customer's full name"},
                    "customer_email": {"type": "string", "description": "Customer's email (optional but recommended)"},
                    "service_name": {"type": "string", "description": "Name of service (e.g. 'Eyebrow Threading')"},
                    "preferred_date": {"type": "string", "description": "Preferred date in YYYY-MM-DD format"},
                    "preferred_time": {"type": "string", "description": "Preferred time (e.g. '10:00', '2:30 PM')"},
                    "notes": {"type": "string", "description": "Any additional notes or preferences"}
                },
                "required": ["customer_name", "service_name", "preferred_date", "preferred_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_bookings",
            "description": "Get the customer's current bookings to find booking IDs for reschedule/cancel.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_reschedule_request",
            "description": "Submit a reschedule request for owner approval. MUST first call get_my_bookings for booking_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "string", "description": "The current booking ID from get_my_bookings"},
                    "new_date": {"type": "string", "description": "New date in YYYY-MM-DD format"},
                    "new_time": {"type": "string", "description": "New time (e.g., '10:00')"},
                    "reason": {"type": "string", "description": "Reason for rescheduling"}
                },
                "required": ["booking_id", "new_date", "new_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment. MUST first call get_my_bookings for booking_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "string", "description": "The booking ID from get_my_bookings"},
                    "reason": {"type": "string", "description": "Reason for cancellation"}
                },
                "required": ["booking_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "report_violation",
            "description": "Report user for abuse/off-topic spam.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Reason for violation"}
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_human_callback",
            "description": "Customer wants to speak to a human/owner/staff directly. Sends email notification to business owner asking them to call the customer back.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why the customer wants to speak to someone (e.g., 'pricing question', 'complaint', 'special request')"
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "How urgent is the callback request. Use 'high' for complaints or time-sensitive matters."
                    }
                },
                "required": ["reason"]
            }
        }
    }
]
