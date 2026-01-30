"""
Saranda Restaurant Function Definitions
========================================
OpenAI-compatible function definitions for the Deepgram Voice Agent.
These are the tools for restaurant order management.
"""


def get_saranda_functions() -> list:
    """
    Returns list of function definitions for Saranda restaurant.
    
    Focused on:
    - Order taking (HITL approval)
    - Reservations (HITL approval)
    - Order changes/cancellations
    - Menu queries
    """
    return [
        # =================================================================
        # ORDER OPERATIONS (HITL Required)
        # =================================================================
        {
            "name": "submit_order",
            "description": "Submit a pickup order to the kitchen for approval. Use after collecting all items and customer name. Kitchen will confirm via WhatsApp. Customer gets SMS when approved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "List of items to order",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Menu item name (e.g., 'Margherita', 'Carbonara')"
                                },
                                "quantity": {
                                    "type": "integer",
                                    "description": "Number of this item"
                                },
                                "modifiers": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Modifiers like 'extra cheese', 'no onion', 'gluten free base'"
                                }
                            },
                            "required": ["name"]
                        }
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Name for the order"
                    },
                    "pickup_time": {
                        "type": "string",
                        "description": "Requested pickup time (e.g., '20 minutes', '7pm'). Leave empty for default estimate."
                    }
                },
                "required": ["items", "customer_name"]
            }
        },
        {
            "name": "request_change",
            "description": "Request a change to an existing order. Kitchen must approve changes. Use when customer wants to add/remove items or modify their order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Original order ID if known"
                    },
                    "change_type": {
                        "type": "string",
                        "enum": ["add_item", "remove_item", "modify", "change_time"],
                        "description": "Type of change requested"
                    },
                    "details": {
                        "type": "string",
                        "description": "Description of what to change (e.g., 'add extra cheese to the Margherita')"
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name to look up order"
                    }
                },
                "required": ["details"]
            }
        },
        {
            "name": "request_cancellation",
            "description": "Request to cancel an order. Kitchen needs to confirm they haven't started cooking yet. Customer will be notified of result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Order ID to cancel"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for cancellation (e.g., 'changed mind', 'ordering elsewhere')"
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name"
                    }
                },
                "required": ["order_id"]
            }
        },
        
        # =================================================================
        # RESERVATIONS (HITL Required)
        # =================================================================
        {
            "name": "request_reservation",
            "description": "Request a table reservation. Staff will confirm availability. Customer gets SMS when approved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Name for the reservation"
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Number of people"
                    },
                    "date": {
                        "type": "string",
                        "description": "Reservation date (e.g., 'Saturday', 'January 20th', 'next Friday')"
                    },
                    "time": {
                        "type": "string",
                        "description": "Reservation time (e.g., '7pm', '7:30 PM')"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Special requests (e.g., 'birthday', 'high chair needed')"
                    }
                },
                "required": ["customer_name", "party_size", "date", "time"]
            }
        },
        
        # =================================================================
        # MENU & INFO QUERIES
        # =================================================================
        {
            "name": "get_menu_info",
            "description": "Get menu information. Use for: pricing questions, ingredient questions, dietary options, what's popular. Can look up specific items or categories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {
                        "type": "string",
                        "description": "Specific item to look up (e.g., 'Margherita', 'Carbonara')"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["pizza", "pizza_speciale", "pasta", "appetizers", "mains", "desserts", "drinks", "kids"],
                        "description": "Menu category to browse"
                    },
                    "query": {
                        "type": "string",
                        "description": "General question about menu (e.g., 'vegetarian options', 'gluten free')"
                    }
                }
            }
        },
        {
            "name": "get_restaurant_info",
            "description": "Get restaurant information like hours, location, delivery options, policies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "enum": ["hours", "location", "delivery", "general"],
                        "description": "Type of info needed"
                    }
                }
            }
        },
        
        # =================================================================
        # CUSTOMER LOOKUP
        # =================================================================
        {
            "name": "lookup_customer",
            "description": "Look up a customer by name to find their profile or previous orders. Use when user says 'It's John' or asks 'Do you have my details?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name or partial name to search for (e.g. 'John', 'Sarah Smith')"
                    },
                    "phone": {
                         "type": "string",
                         "description": "Optional: Phone number if the user provides it (e.g., '0412345678')"
                    }
                },
                "required": ["name"]
            }
        },
        
        # =================================================================
        # CALL CONTROL
        # =================================================================
        {
            "name": "flag_off_topic",
            "description": "Call when customer is off-topic (flirting, personal questions) OR complementary (e.g. 'you are sweet'). System handles each appropriately (warnings for abuse, polite thanks for compliments).",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Category: 'flirting', 'personal', 'compliment', 'benign_chatter'"
                    }
                },
                "required": ["reason"]
            }
        },
        {
            "name": "transfer_to_staff",
            "description": "Transfer call to restaurant staff. Use ONLY when: (1) customer EXPLICITLY asks to speak to a person/human, or (2) you are completely unable to assist after multiple attempts. Do NOT use just because the user corrects you or says 'no'.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "end_call",
            "description": "End the call gracefully after customer is done. Say goodbye first, then call this.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    ]
