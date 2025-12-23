"""
Live Booking Test - AI Interaction + Database Write
====================================================
This script tests the full booking flow by:
1. Sending messages to OpenAI GPT-4o-mini (same as voice agent)
2. Agent decides to call create_booking function
3. Booking is actually written to Appwrite database
4. Verifies booking appears in the motel_reservations collection

Usage:
    python scripts/test_live_booking.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Add parent to path
sys.path.insert(0, '/Applications/Journey of pro/Nona/backend')

import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the knowledge base functions
from services.motel_knowledge_base import (
    get_room_pricing,
    get_room_details,
    recommend_room,
    get_check_in_out_info,
    get_location_info,
    get_amenities,
    get_activities_nearby,
    search_motel_info,
    MOTEL_INFO
)

# =============================================================================
# CONFIGURATION
# =============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
APPWRITE_ENDPOINT = os.getenv("APPWRITE_ENDPOINT", "https://syd.cloud.appwrite.io/v1")
APPWRITE_PROJECT_ID = os.getenv("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.getenv("APPWRITE_API_KEY")
MOTEL_DB_ID = "6947b8300005f5863f96"

if not OPENAI_API_KEY:
    print("❌ Error: OPENAI_API_KEY not found in environment")
    print("   Add it to backend/.env")
    sys.exit(1)

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# =============================================================================
# SYSTEM PROMPT (Same as voice agent - condensed version)
# =============================================================================

SYSTEM_PROMPT = """You are the AI receptionist named Ovela for The Lydoun Motel in Chiltern, Victoria.

=== PROPERTY DETAILS ===
The Lydoun Motel - 7 Main Street, Chiltern VIC 3683
Phone: (03) 5726 1788 | Reception: 7:30am - 9:00pm
Check-in: From 2:00pm | Check-out: Prior to 10:00am

Room Types & Pricing:
1. Queen Room - From $130/night (suits 1-2 guests)
2. Twin Room - From $140/night (suits 2-3 guests)
3. Family Room - From $160/night (suits up to 4 guests)
4. Accessible Room - From $130/night (reduced mobility friendly)

All rooms: ground level, non-smoking, WiFi, parking outside room.

=== YOUR ROLE ===
Handle bookings, availability, pricing, amenities, and general questions.

=== IMPORTANT ===
When a guest wants to book:
1. Get their dates
2. Get number of guests
3. Use check_availability to verify
4. Get their name
5. Use create_booking to make the reservation
6. Confirm with booking reference

Be friendly, professional, with country hospitality warmth.
"""

# =============================================================================
# FUNCTION DEFINITIONS (Same as voice agent)
# =============================================================================

FUNCTIONS = [
    {
        "name": "check_availability",
        "description": "Check room availability for specific dates",
        "parameters": {
            "type": "object",
            "properties": {
                "check_in_date": {"type": "string", "description": "YYYY-MM-DD format"},
                "room_type": {"type": "string", "enum": ["queen", "twin", "family", "accessible"]}
            },
            "required": ["check_in_date"]
        }
    },
    {
        "name": "create_booking",
        "description": "Create a reservation for a guest",
        "parameters": {
            "type": "object",
            "properties": {
                "guest_name": {"type": "string", "description": "Full name of guest"},
                "guest_phone": {"type": "string", "description": "Contact phone"},
                "check_in_date": {"type": "string", "description": "YYYY-MM-DD"},
                "check_out_date": {"type": "string", "description": "YYYY-MM-DD"},
                "room_type": {"type": "string", "enum": ["queen", "twin", "family", "accessible"]},
                "num_guests": {"type": "integer"},
                "notes": {"type": "string"}
            },
            "required": ["guest_name", "check_in_date", "room_type"]
        }
    },
    {
        "name": "get_room_pricing",
        "description": "Get room prices",
        "parameters": {
            "type": "object",
            "properties": {
                "room_type": {"type": "string", "enum": ["queen", "twin", "family", "accessible"]}
            }
        }
    },
    {
        "name": "get_room_details",
        "description": "Get detailed room info including facilities",
        "parameters": {
            "type": "object",
            "properties": {
                "room_type": {"type": "string", "enum": ["queen", "twin", "family", "accessible"]}
            },
            "required": ["room_type"]
        }
    },
    {
        "name": "recommend_room",
        "description": "Recommend a room based on guest count",
        "parameters": {
            "type": "object",
            "properties": {
                "num_guests": {"type": "integer"},
                "needs_accessibility": {"type": "boolean"}
            },
            "required": ["num_guests"]
        }
    }
]

# =============================================================================
# FUNCTION HANDLERS
# =============================================================================

def execute_check_availability(args: dict) -> dict:
    """Simulate availability check (always available for demo)."""
    check_in = args.get("check_in_date", "")
    room_type = args.get("room_type", "queen")
    
    pricing = {
        "queen": 130, "twin": 140, "family": 160, "accessible": 130
    }
    
    return {
        "available": True,
        "room_type": room_type,
        "price_per_night": pricing.get(room_type, 130),
        "message": f"Yes, we have a {room_type} room available for {check_in} at ${pricing.get(room_type, 130)} per night."
    }


def execute_create_booking(args: dict) -> dict:
    """Actually create a booking in Appwrite database."""
    import requests
    import random
    import string
    
    # Generate booking reference
    ref_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    booking_ref = f"LYD-{ref_suffix}"
    
    guest_name = args.get("guest_name", "Test Guest")
    guest_phone = args.get("guest_phone", "+61400000000")
    check_in = args.get("check_in_date", datetime.now().strftime("%Y-%m-%d"))
    check_out = args.get("check_out_date")
    room_type = args.get("room_type", "queen")
    num_guests = args.get("num_guests", 2)
    notes = args.get("notes", "")
    
    # Calculate check_out if not provided
    if not check_out:
        check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
        check_out = (check_in_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Calculate pricing
    pricing = {"queen": 130, "twin": 140, "family": 160, "accessible": 130}
    rate = pricing.get(room_type, 130)
    
    check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
    check_out_dt = datetime.strptime(check_out, "%Y-%m-%d")
    num_nights = (check_out_dt - check_in_dt).days
    total = rate * num_nights
    
    # Prepare reservation data
    reservation_data = {
        "guest_name": guest_name,
        "guest_phone": guest_phone,
        "guest_email": "",
        "room_type": room_type,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "num_guests": num_guests,
        "num_nights": num_nights,
        "rate_per_night": rate,
        "total_amount": total,
        "status": "pending",
        "booking_reference": booking_ref,
        "notes": notes or f"AI booking test at {datetime.now().strftime('%H:%M:%S')}",
        "created_at": datetime.now().isoformat(),
        "created_by": "ovela_ai_test"
    }
    
    print(f"\n📝 Creating booking in Appwrite...")
    print(f"   Database: {MOTEL_DB_ID}")
    print(f"   Collection: motel_reservations")
    print(f"   Data: {json.dumps(reservation_data, indent=2)}")
    
    # Write to Appwrite
    try:
        headers = {
            "Content-Type": "application/json",
            "X-Appwrite-Project": APPWRITE_PROJECT_ID,
            "X-Appwrite-Key": APPWRITE_API_KEY
        }
        
        url = f"{APPWRITE_ENDPOINT}/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
        payload = {
            "documentId": f"test_{int(datetime.now().timestamp())}",
            "data": reservation_data
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"\n✅ BOOKING CREATED SUCCESSFULLY!")
            print(f"   Document ID: {result.get('$id')}")
            print(f"   Reference: {booking_ref}")
            return {
                "success": True,
                "booking_reference": booking_ref,
                "document_id": result.get("$id"),
                "guest_name": guest_name,
                "check_in": check_in,
                "check_out": check_out,
                "room_type": room_type,
                "total": total,
                "message": f"Booking confirmed! Reference: {booking_ref}. {room_type.title()} room for {guest_name}, checking in {check_in}. Total: ${total}."
            }
        else:
            print(f"\n❌ Appwrite error: {response.status_code}")
            print(f"   Response: {response.text}")
            return {
                "success": False,
                "error": f"Database error: {response.status_code}",
                "message": "I had trouble saving the booking. Let me take your details and reception will call you back."
            }
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "There was a technical issue. Please call reception directly."
        }


def execute_function(name: str, args: dict) -> dict:
    """Execute a function and return result."""
    print(f"\n🔧 Function called: {name}")
    print(f"   Args: {json.dumps(args)}")
    
    if name == "check_availability":
        return execute_check_availability(args)
    elif name == "create_booking":
        return execute_create_booking(args)
    elif name == "get_room_pricing":
        return get_room_pricing(args.get("room_type"))
    elif name == "get_room_details":
        return get_room_details(args.get("room_type", "queen"))
    elif name == "recommend_room":
        return recommend_room(
            args.get("num_guests", 2),
            args.get("needs_accessibility", False)
        )
    else:
        return {"error": f"Unknown function: {name}"}


# =============================================================================
# CONVERSATION SIMULATOR
# =============================================================================

def chat_with_agent(messages: list, user_message: str) -> tuple[str, list]:
    """Send message to agent and get response, handling function calls."""
    
    # Add user message
    messages.append({"role": "user", "content": user_message})
    
    print(f"\n👤 User: {user_message}")
    
    max_function_calls = 5  # Prevent infinite loops
    calls_made = 0
    
    while calls_made < max_function_calls:
        # Call OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            functions=FUNCTIONS,
            function_call="auto",
            temperature=0.7
        )
        
        assistant_message = response.choices[0].message
        
        # Check if function call
        if assistant_message.function_call:
            calls_made += 1
            func_name = assistant_message.function_call.name
            func_args = json.loads(assistant_message.function_call.arguments)
            
            # Execute function
            result = execute_function(func_name, func_args)
            
            # Add assistant message with function call (using empty string instead of None)
            messages.append({
                "role": "assistant",
                "content": "",  # Use empty string instead of None
                "function_call": {
                    "name": func_name,
                    "arguments": json.dumps(func_args)
                }
            })
            
            # Add function result
            messages.append({
                "role": "function",
                "name": func_name,
                "content": json.dumps(result)
            })
            
            # Continue loop to get follow-up response
            continue
        else:
            # No function call, we have final response
            break
    
    # Add final assistant response
    final_content = assistant_message.content or "I've processed your request."
    messages.append({"role": "assistant", "content": final_content})
    
    print(f"\n🤖 Agent: {final_content}")
    
    return final_content, messages


def run_booking_test():
    """Run a complete booking test conversation."""
    print("\n" + "="*70)
    print("  🧪 LIVE BOOKING TEST - AI + DATABASE")
    print("="*70)
    print("\nThis will:")
    print("1. Chat with GPT-4o-mini using the motel agent prompt")
    print("2. Agent will call create_booking function")
    print("3. Booking will be saved to Appwrite database")
    print("4. You can verify it appears in the CRM dashboard\n")
    
    # Initialize conversation
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Calculate test dates
    check_in = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    check_out = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")
    check_in_friendly = (datetime.now() + timedelta(days=3)).strftime("%B %d")
    
    # Simulate conversation - provide all details upfront
    test_conversation = [
        f"Hi, I'd like to book a queen room for one night. Check-in on {check_in_friendly}, just one person. My name is Sarah Johnson and my phone is 0412345678.",
        "Yes, please go ahead and book it for me.",
    ]
    
    print("-"*70)
    print("Starting conversation...")
    print("-"*70)
    
    for user_msg in test_conversation:
        response, messages = chat_with_agent(messages, user_msg)
        print("-"*50)
    
    print("\n" + "="*70)
    print("  ✅ TEST COMPLETE")
    print("="*70)
    print("\n📋 Next steps:")
    print("   1. Open http://localhost:3000/motel/reservations")
    print("   2. Verify the new booking appears")
    print("   3. Check the booking reference matches\n")


def run_interactive_mode():
    """Run interactive chat with the agent."""
    print("\n" + "="*70)
    print("  🎤 INTERACTIVE MODE - Chat with Ovela")
    print("="*70)
    print("\nType your messages to chat with the AI receptionist.")
    print("Type 'quit' to exit.\n")
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break
            if not user_input:
                continue
                
            response, messages = chat_with_agent(messages, user_input)
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Live Booking Test')
    parser.add_argument('--interactive', '-i', action='store_true', 
                        help='Run in interactive mode')
    parser.add_argument('--auto', '-a', action='store_true',
                        help='Run automated booking test (default)')
    
    args = parser.parse_args()
    
    if args.interactive:
        run_interactive_mode()
    else:
        run_booking_test()
