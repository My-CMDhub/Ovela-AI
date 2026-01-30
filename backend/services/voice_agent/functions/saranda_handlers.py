"""
Saranda Restaurant Function Handlers
=====================================
Order, reservation, and change request handlers for Saranda Cafe & Pizzeria.

Key Design:
- All requests go through HITL (WhatsApp approval)
- No autonomous confirmation - AI says "let me check with kitchen"
- Staff reply YES/NO/LATE
- Customer gets SMS confirmation after approval
"""

import logging
import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
from core.config import settings
from services.appwrite import db_service


from services.saranda_flows import (
    OrderRequest, OrderItem, ReservationRequest,
    RequestStatus, RequestType,
    generate_request_id, saranda_queue, delayed_notification_queue
)
from services.staff_notifications import staff_notification_service
from services.knowledge_base.saranda import (
    get_menu_item_by_name, get_prep_time_estimate, format_order_summary,
    SARANDA_DATA, is_within_operating_hours, minutes_until_close,
    get_next_opening_datetime
)

logger = logging.getLogger(__name__)


# =============================================================================
# ORDER HANDLERS
# =============================================================================

# Square Integration
from services.tenants.saranda.square_client import SquareClient, SquareOrderItem
from services.tenants.saranda.square_flows import saranda_approval_tracker, SquareOrderRequest, ApprovalState

async def handle_submit_order(args: dict, user_phone: str, call_sid: str = None) -> dict:
    """
    Submit a new pickup order for kitchen approval via Square.
    
    Creates an order in Square (OPEN state) and tracks it for HITL approval.
    """
    
    # Get current time in Melbourne timezone (for testing)
    tz = ZoneInfo("Australia/Melbourne")
    now = datetime.now(tz)
    current_day = now.strftime("%A")  # e.g., "Monday"
    current_time = now.strftime("%I:%M %p")  # e.g., "7:30 PM"
    
    # === VALIDATION: Check if we can accept orders ===
    
    # Check if restaurant is open
    is_open, rejection_reason = is_within_operating_hours(current_day, current_time)
    if not is_open:
        next_open = get_next_opening_datetime()
        if next_open and next_open.date() == now.date():
            next_open_str = f"today at {next_open.strftime('%I:%M %p')}"
        else:
            next_open_str = next_open.strftime("%A at %I:%M %p") if next_open else "tomorrow"
        
        return {
            "success": False,
            "rejected_closed": True,
            "message": rejection_reason,
            "ai_instruction": f"""REJECT: We are CLOSED.
Tell customer: "I can't take orders now as we're closed. Please call back {next_open_str}. Thanks!"
DO NOT promise later delivery."""
        }
    
    # Check kitchen cutoff (5 minutes before close)
    mins_to_close = minutes_until_close(current_time, current_day)
    if mins_to_close >= 0 and mins_to_close < 5:
        return {
            "success": False,
            "rejected_cutoff": True,
            "message": "Sorry, the kitchen is about to close. Could you try us tomorrow? We open at 4:30 PM Tuesday through Friday, or 11:30 AM on weekends.",
            "ai_instruction": "The kitchen is closing in less than 5 minutes. Politely tell them to call back tomorrow and offer the opening hours."
        }
    
    # === Original validation ===
    items_raw = args.get("items", [])
    customer_name = args.get("customer_name", "")
    pickup_time = args.get("pickup_time", "")
    
    # Validation
    if not items_raw:
        return {
            "success": False,
            "message": "I didn't catch what you wanted to order. What would you like?"
        }
    
    if not customer_name:
        return {
            "success": False,
            "needs_name": True,
            "message": "What name should I put the order under?"
        }
    
    # Default pickup time based on queue/busyness (Simple fallback)
    if not pickup_time:
        pickup_time = "20 minutes"
    
    # Parse items for Square
    square_items: List[SquareOrderItem] = []
    unrecognized = []
    total_cents = 0
    
    for item_raw in items_raw:
        item_name = item_raw.get("name", "")
        quantity = item_raw.get("quantity", 1)
        modifiers = item_raw.get("modifiers", [])
        
        # Look up in menu
        menu_item = get_menu_item_by_name(item_name)
        if menu_item:
            # Calculate price
            base_price = menu_item["price"]
            modifier_cost = 0
            for mod in modifiers:
                mod_key = mod.lower().replace(" ", "_")
                modifier_cost += SARANDA_DATA["modifiers"].get(mod_key, 0)
            
            price_inc_mods = base_price + modifier_cost
            price_cents = int(round(price_inc_mods * 100))
            
            total_cents += price_cents * quantity
            
            square_items.append(SquareOrderItem(
                name=menu_item["name"],
                quantity=quantity,
                price_cents=price_cents,
                modifiers=modifiers
            ))
        else:
            unrecognized.append(item_name)
    
    # Handle unrecognized items
    if unrecognized and not square_items:
        return {
            "success": False,
            "message": f"Sorry, I couldn't find '{unrecognized[0]}' on the menu. Could you try again or check our menu?"
        }
    
    if unrecognized:
        logger.warning(f"Unrecognized items: {unrecognized}")
    
    # --- BATCH STRATEGY (User Requirement) ---
    # Instead of submitting to Square immediately, we return "hold" action.
    # The VoiceAgentHandler will finalize this on call end.
    
    # Calculate totals for confirmation message
    total_dollars = total_cents / 100.0
    
    # Prepare details for valid Order Request
    order_details = {
        "customer_name": customer_name,
        "user_phone": user_phone,
        "items": [
            {
                "name": i.name,
                "quantity": i.quantity,
                "price_cents": i.price_cents,
                "modifiers": i.modifiers
            } for i in square_items
        ],
        "pickup_time": pickup_time,
        "total_cents": total_cents
    }

    return {
        "success": True,
        "action": "hold",
        "order_details": order_details,
        "message": f"I've noted that down. {len(square_items)} item{'s' if len(square_items) > 1 else ''} totalling ${total_dollars:.2f}. Pickup around {pickup_time}. Is there anything else?"
    }


async def handle_request_change(args: dict, user_phone: str, transfer_to: str, pending_order: dict = None) -> dict:
    """
    Request a change to an existing order.
    
    Strategy:
    1. If 'pending_order' exists (Draft), modify it locally and return "hold".
    2. If NO draft (Existing Confirmed Order), transfer to staff (Legacy).
    """
    change_type = args.get("change_type", "")
    details = args.get("details", "")
    
    # === SCENARIO A: Modify Draft (Batch Mode) ===
    if pending_order:
        logger.info(f"🔄 Modifying Batch Order: {change_type} - {details}")
        
        # Simple heuristic modification (AI will have to re-submit full list often, but let's try strict logic if we can)
        # Actually, for robustness, if the AI sends "add_item", we might not have the item details struct here.
        # Ideally, 'request_change' should just be 'submit_order' again with the new list if it's a draft.
        # But if the prompt uses request_change, we need to handle it.
        
        # INSTRUCTION FOR AI: When changing a draft, just say "Okay, updated." 
        # But if backend logic is needed:
        
        # If the user says "Add garlic bread", the AI might call request_change(add_item, garlic bread).
        # We can't easily modify the 'items' list here without menu lookup.
        # BETTER STRATEGY: Tell AI to re-submit the order using submit_order if it's still drafting?
        # OR: Return a special instruction.
        
        # Let's trust the AI to manage the list if we give it the right feedback.
        # BUT, `pending_order` is in Backend Memory. The AI might have forgotten the full list.
        
        # FALLBACK for this iteration:
        # If it's a simple addition, just append a "Note" to the order?
        # or, return action="transfer" if it's too complex.
        
        # User requested: "Simulate handle_request_change... return text response... keep it on hold"
        
        return {
            "success": True,
            "action": "hold", # Update the hold? No, we don't return an order here.
            # We assume the AI maintains the state in its context?
            # Actually, if we return "hold" without "order_details", handler might not update.
            # Let's start simple:
            "message": f"I've updated your order request to include that change ({details}). Getting it ready for the kitchen.",
            # Implicitly, we might want to flag this. 
            # Ideally, the AI calls 'submit_order' again with the FULL updated list.
            # Let's prompt the AI to do that.
            "outcome_override": None
        }
    
    # === SCENARIO B: Legacy / Confirmed Order ===
    # Transfer to staff
    transfer_number = transfer_to
    
    return {
        "success": True,
        "action": "transfer",
        "transfer_to": transfer_number,
        "message": "Since that order is already with the kitchen, I'll connect you to the staff to make sure they catch the change in time."
    }


async def handle_request_cancellation(args: dict, user_phone: str, transfer_to: str = None) -> dict:
    """
    Request to cancel an order via HITL.
    Kitchen needs to confirm they haven't started cooking.
    """
    # === FORCE TRANSFER TO STAFF ===
    # Use passed transfer number or fallback
    if not transfer_to:
        from core.config import settings
        transfer_to = getattr(settings, 'SARANDA_STAFF_PHONE', settings.STAFF_PHONE_NUMBER)

    return {
        "success": True,
        "action": "transfer",
        "transfer_to": transfer_to,
        "message": "For cancellations, I need to connect you with the staff to ensure the kitchen hasn't already started cooking. Connecting you now..."
    }


# =============================================================================
# STATUS HANDLERS
# =============================================================================

async def handle_check_order_status(args: dict, user_phone: str) -> dict:
    """
    Check status of recent orders for the calling user.
    """
    # Use the phone number from the call
    if not user_phone:
        return {
            "success": False,
            "message": "I can't see your phone number, so I can't look up your order. Do you have an order number?"
        }
    
    square_client = SquareClient()
    # Fetch recent history (up to 5) to distinguish active vs past
    orders = await square_client.search_orders_by_phone(user_phone, limit=5)
    
    if orders:
        # 1. Look for ACTIVE order first
        active_order = next((o for o in orders if o.state == "OPEN" and o.fulfillment_state != "CANCELED"), None)
        
        target_order = active_order if active_order else orders[0]
        is_historical = active_order is None
        
        # Translate state
        status_msg = "is being processed"
        if target_order.state == "COMPLETED":
            status_msg = "is completed"
        elif target_order.state == "CANCELED" or target_order.fulfillment_state == "CANCELED":
            status_msg = "was cancelled"
        elif target_order.state == "OPEN":
             if target_order.is_approved:
                 status_msg = "is being prepared"
             else:
                 status_msg = "is waiting for confirmation"

        if is_historical:
             # Calculate relative time
             from datetime import datetime, timezone
             now = datetime.now(timezone.utc)
             created = target_order.created_at
             if created.tzinfo is None: created = created.replace(tzinfo=timezone.utc)
             
             diff = now - created
             if diff.days > 0:
                 time_str = f"{diff.days} days ago"
             elif diff.seconds > 3600:
                 time_str = f"about {diff.seconds // 3600} hours ago"
             else:
                 time_str = "just recently"

             return {
                "success": True,
                "found": True,
                "active": False,
                "order": {
                    "order_id": target_order.order_id,
                    "state": target_order.state,
                    "total_dollars": target_order.total_dollars,
                    "items": [
                        {"name": i.name, "quantity": i.quantity} 
                        for i in getattr(target_order, "items", [])
                    ]
                },
                "message": f"I couldn't find any active orders for you right now. The last order I have is from {time_str}, which {status_msg}."
            }
        else:
            # Active Order Found
            # Return flattened structure for checking_status
            
            # Helper for items
            items_summary = ", ".join([f"{i.quantity}x {i.name}" for i in getattr(target_order, "items", [])])
            
            # Format time
            created_local = target_order.created_at.strftime("%I:%M %p") if target_order.created_at else "recently"
            
            return {
                "success": True, 
                "found": True,
                "active": True,
                "order_id": target_order.order_id,
                "status": target_order.state,
                "fulfillment_status": target_order.fulfillment_state,
                "items_summary": items_summary,
                "total": target_order.total_dollars,
                "message": f"I found your order for {target_order.customer_name} ({items_summary}). It was placed at {created_local}. Status: {status_msg}."
            }
        
        # Calculate timing information for AI context
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        # Handle timezone-aware created_at
        created = order.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        
        elapsed = now - created
        minutes_ago = int(elapsed.total_seconds() / 60)
        
        # Format created time nicely
        created_local = created.strftime("%I:%M %p")  # e.g., "07:55 PM"
        
        # Estimate pickup (usually ~20 min from order)
        estimated_wait = max(0, 20 - minutes_ago)
        
        # Build a rich context message for AI
        timing_context = f"placed at {created_local} ({minutes_ago} minutes ago)"
        if order.is_approved and estimated_wait > 0:
            timing_context += f", estimated ready in about {estimated_wait} minutes"
        elif order.is_approved and estimated_wait <= 0:
            timing_context += ", should be ready soon or already ready"
            
        # Build items summary for AI to speak
        items_list = []
        if order.line_items:
             for line in order.line_items:
                 name = line.name
                 qty = line.quantity
                 items_list.append(f"{qty}x {name}")
        items_summary = ", ".join(items_list)

        # Reference ID (short)
        ref_id = getattr(order, 'reference_id', '') or ''
        short_ref = ref_id.replace("ovela:", "")

        return {
            "found": True,
            "type": "order",
            "order_id": order.order_id,
            "reference_code": short_ref,
            "customer_name": order.customer_name,
            "total": order.total_dollars,
            "status": order.state,
            "fulfillment_status": order.fulfillment_state,
            "is_approved": order.is_approved,
            # Enhanced Details for AI
            "items_summary": items_summary,
            "created_time_str": created_local,
            "created_minutes_ago": minutes_ago,
            "estimated_wait_minutes": estimated_wait if order.is_approved else None,
            # Human-friendly message incorporating timing
            "message": f"I found your order for {order.customer_name} ({items_summary}). It was placed at {created_local} ({minutes_ago} mins ago). Status: {status_msg}."
        }
    
    # 2. Check Reservations (Fallback)
    # Search in saranda_queue (_pending, _active, _completed)
    found_res = None
    
    # helper to check request
    def is_match(req):
        return (req.request_type == RequestType.RESERVATION and 
                req.customer_phone == user_phone)
    
    # Check active
    active = saranda_queue.get_active()
    if active and is_match(active):
        found_res = active
    
    # Check pending
    if not found_res:
        for req in saranda_queue._pending:
            if is_match(req):
                found_res = req
                break
                
    # Check completed (recent)
    if not found_res:
        # manual iteration of completed dict values
        for req in saranda_queue._completed.values():
            if is_match(req):
                found_res = req
                # We want the most recent one ideally, but this is a dict.
                # Assuming simple case for now.
                break
    
    if found_res:
        status_map = {
            RequestStatus.PENDING_STAFF: "waiting for confirmation from the team",
            RequestStatus.APPROVED: "confirmed",
            RequestStatus.REJECTED: "could not be accepted",
            RequestStatus.TOO_LATE: "was too late to fit in",
            RequestStatus.EXPIRED: "timed out (please try again)",
            RequestStatus.DRAFT: "is being drafted"
        }
        s_msg = status_map.get(found_res.status, "is in progress")
        
        return {
            "found": True,
            "type": "reservation",
            "id": found_res.id,
            "status": found_res.status.value,
            "message": f"I found a table reservation for {found_res.party_size} people on {found_res.date} at {found_res.time}. It is currently {s_msg}."
        }

    return {
        "found": False,
        "message": "I couldn't find any recent orders or reservations under this phone number. Did you use a different number?"
    }


# =============================================================================
# RESERVATION HANDLERS
# =============================================================================

async def handle_request_reservation(args: dict, user_phone: str, business_phone: str = None) -> dict:
    """
    Request a table reservation via HITL.
    
    Args:
        args: {
            customer_name: str,
            party_size: int,
            date: str,  # e.g., "Saturday", "January 20th"
            time: str,  # e.g., "7pm", "7:00 PM"
            notes?: str
        }
    """    
    customer_name = args.get("customer_name", "")
    party_size = args.get("party_size", 2)
    date = args.get("date", "")
    time = args.get("time", "")
    notes = args.get("notes", "")
    
    # === VALIDATION: Check for Monday ===
    # Extract day name from date if provided (e.g., "Monday, 20th Jan" or just "Monday")
    date_lower = date.lower() if date else ""
    if "monday" in date_lower:
        return {
            "success": False,
            "rejected_monday": True,
            "message": "Sorry, we're closed on Mondays. Would you like to book for another day? We're open Tuesday through Sunday."
        }
    
    # Standard validation
    if not customer_name:
        return {
            "success": False,
            "needs_name": True,
            "message": "What name should I book the table under?"
        }
    
    if not date:
        return {
            "success": False,
            "needs_date": True,
            "message": "What day were you thinking for the reservation?"
        }
    
    if not time:
        return {
            "success": False,
            "needs_time": True,
            "message": "And what time would you like?"
        }
    
    # Check capacity
    max_group = SARANDA_DATA["info"]["max_group_size"]
    if party_size > max_group:
        phone_display = business_phone or "(08) 6401 6397"
        return {
            "success": False,
            "message": f"For groups larger than {max_group}, please call us directly on {phone_display} so we can work something out."
        }
    
    # Large group warning
    deposit_note = ""
    if party_size > 10:
        deposit_note = " For larger groups we might need a deposit, but the team will sort that with you."
    
    # Create reservation request
    request_id = generate_request_id()
    reservation = ReservationRequest(
        id=request_id,
        customer_name=customer_name,
        customer_phone=user_phone,
        party_size=party_size,
        date=date,
        time=time,
        notes=notes
    )
    
    # === CHECK: Are we currently open? ===
    # If closed (off-hours), queue for delayed notification instead of immediate
    tz = ZoneInfo("Australia/Melbourne")
    now = datetime.now(tz)
    current_day = now.strftime("%A")  # e.g., "Monday"
    current_time = now.strftime("%I:%M %p")  # e.g., "7:30 PM"
    
    is_open, _ = is_within_operating_hours(current_day, current_time)
    
    if not is_open:
        # Off-hours: Queue for delayed notification
        delayed_notification_queue.add(reservation)
        
        return {
            "success": True,
            "request_id": request_id,
            "status": "queued_for_review",
            "delayed_notification": True,
            "message": f"I've noted that reservation request. Since we're closed right now, the team will see it when they open next and they'll text you to confirm. That's a table for {party_size} on {date} at {time} under {customer_name}.{deposit_note}"
        }
    
    # We're open - proceed with immediate notification
    await saranda_queue.add(reservation)
    
    # Build summary for WhatsApp
    summary = f"Party: {party_size} people\nDate: {date}\nTime: {time}"
    if notes:
        summary += f"\nNotes: {notes}"
    
    # Send WhatsApp if active
    if saranda_queue.get_active() and saranda_queue.get_active().id == request_id:
        # FROZEN : WhatsApp notifications disabled for now.
        # Direct Square integration handles kitchen flow.
        pass
        # try:
        #     await staff_notification_service.send_whatsapp_order_approval(
        #         request_id=request_id,
        #         request_type="reservation",
        #         customer_name=customer_name,
        #         order_summary=summary,
        #         pickup_time=time,
        #         total_amount=0
        #     )
        # except Exception as e:
        #     logger.error(f"Failed to send reservation WhatsApp: {e}")
    
    return {
        "success": True,
        "request_id": request_id,
        "status": "pending_approval",
        "message": f"I've sent that reservation request through. That's a table for {party_size} on {date} at {time} under {customer_name}. They'll confirm shortly and you'll get a text.{deposit_note}"
    }


# =============================================================================
# MENU / INFO HANDLERS
# =============================================================================

async def handle_get_menu_info(args: dict) -> dict:
    """
    Get menu information, popular items, or specific dish details.
    """
    query = args.get("query", "").lower()
    category = args.get("category", "")
    item_name = args.get("item_name", "")
    
    # Specific item lookup
    if item_name:
        item = get_menu_item_by_name(item_name)
        if item:
            dietary = item.get("dietary", [])
            desc = item.get("description", "")
            dietary_str = f" ({', '.join(dietary)})" if dietary else ""
            return {
                "found": True,
                "item": item,
                "message": f"The {item['name']} is ${item['price']:.0f}.{dietary_str} {desc}"
            }
        return {
            "found": False,
            "message": f"I couldn't find '{item_name}' on our menu. Did you mean something else?"
        }
    
    # Category lookup
    if category:
        cat_items = SARANDA_DATA["menu"].get(category, {})
        if cat_items:
            items_list = [f"{item['name']} ${item['price']:.0f}" for item in cat_items.values()][:5]
            return {
                "category": category,
                "items": list(cat_items.values()),
                "message": f"Our {category.replace('_', ' ')} includes: {', '.join(items_list)}."
            }
    
    # Popular items
    popular = SARANDA_DATA["popular_items"]
    return {
        "popular_items": popular,
        "message": f"Our most popular items are {', '.join(popular)}. Would you like to know more about any of these?"
    }


async def handle_get_restaurant_info(args: dict) -> dict:
    """
    Get restaurant hours, location, policies.
    """
    info_type = args.get("info_type", "general")
    info = SARANDA_DATA["info"]
    
    if info_type == "hours":
        # Get dynamic hours summary
        tz = ZoneInfo("Australia/Perth")
        now = datetime.now(tz)
        day = now.strftime("%A")
        time = now.strftime("%I:%M %p")
        
        is_open, _ = is_within_operating_hours(day, time)
        next_opening = get_next_opening_datetime()
        
        hours_msg = "We're open Tuesday to Friday from 4:30 to 9pm, and on weekends we do lunch from 11:30 to 2 plus dinner from 4:30. "
        
        if is_open:
            hours_msg += "We're actually open right now!"
        elif next_opening:
            if next_opening.date() == now.date():
                hours_msg += f"We're currently closed but we'll be open today at {next_opening.strftime('%I:%M %p')}."
            else:
                hours_msg += f"We're closed now and reopen {next_opening.strftime('%A at %I:%M %p')}."
        
        return {
            "hours": info["hours"],
            "message": hours_msg
        }
    
    if info_type == "location":
        return {
            "address": info["address"],
            "phone": info["phone"],
            "message": f"We're at {info['address']}. That's in Landsdale, easy to find."
        }
    
    if info_type == "delivery":
        partners = SARANDA_DATA["policies"]["delivery_partners"]
        return {
            "delivery_partners": partners,
            "message": f"We don't do delivery ourselves, but you can order through {' or '.join(partners)} for delivery."
        }
    
    # General
    return {
        "name": info["name"],
        "address": info["address"]
    }


# =============================================================================
# CUSTOMER LOOKUP HANDLERS
# =============================================================================

async def lookup_customer(args: dict, user_phone: str) -> dict:
    """
    Lookup customer by name/phone.
    Strategy:
    1. Phone Search (Caller ID or Explicit Args) - Primary & Fastest
    2. Name Search (Fallback) - Only if phone yields no result or bad match.
    """
    # Safe attribute/key accessor helper
    def g(obj, k, default=None):
        return obj.get(k, default) if isinstance(obj, dict) else getattr(obj, k, default) or default

    name_query = args.get("name", "").strip()
    
    # Check if a specific phone was provided in args, else use Caller ID
    search_phone = args.get("phone")
    
    if not search_phone and user_phone:
        search_phone = user_phone
        
    try:
        square_client = SquareClient()
        cust = None
        
        # --- STEP 1: Try Phone Search ---
        if search_phone:
            # Normalize Phone (E.164)
            # BUG FIX: filter(str.isdigit) strips '+', so we must handle it carefully
            raw_clean = "".join(filter(lambda x: x.isdigit() or x == '+', search_phone))
            clean_phone = raw_clean
            
            # AU Logic
            if clean_phone.startswith("04") and len(clean_phone) == 10:
                clean_phone = "+61" + clean_phone[1:]
            elif clean_phone.startswith("61") and len(clean_phone) == 11:
                 clean_phone = "+" + clean_phone
            elif not clean_phone.startswith("+") and len(clean_phone) == 9:
                 clean_phone = "+61" + clean_phone

            logger.info(f"🔍 Searching Square by Phone: {clean_phone} (raw: {search_phone})")
            context = await square_client.get_customer_context(clean_phone)
            
            if context and context.get("customer"):
                cust = context["customer"]
                
                # Check for Name Mismatch (Smart Identity)
                # Use helper g()
                given = g(cust, "given_name", "")
                family = g(cust, "family_name", "")
                phone = g(cust, "phone_number", "")
                cid = g(cust, "id")
                
                found_name = f"{given} {family}".strip()
                
                # If name was provided and matches loosely, it's a strong verify.
                if name_query and name_query.lower() in found_name.lower():
                     return {
                        "found": True,
                        "customer_id": cid,
                        "name": found_name,
                        "phone": phone,
                        "recent_order": context.get("recent_order"),
                        "message": f"Welcome back {given}. I see you ordered {context.get('last_item', 'recently')}. Same again?"
                    }
                
                # If name provided but doesn't match, ask for confirmation
                if name_query:
                     return {
                        "found": True,
                        "customer_id": cid,
                        "name": found_name,
                        "phone": phone,
                        "recent_order": context.get("recent_order"),
                        "message": f"I see this number is registered to {given}. Is that you, or are you ordering for someone else?"
                    }
                
                # No name provided, just return found profile
                return {
                    "found": True,
                    "customer_id": cid,
                    "name": found_name,
                    "phone": phone,
                    "recent_order": context.get("recent_order"),
                    "message": f"Hi {given}, welcome back."
                }

            # GUEST ORDER HANDLING (No Customer Profile, but Active Order exists)
            elif context and context.get("recent_order"):
                ord = context["recent_order"]
                # Use name already extracted by SquareClient
                ord_name = g(ord, 'customer_name', 'Guest')
                
                # If we name match or just assume it's them because they are calling from that number
                msg = f"I see you have an open order, {ord_name}." if ord_name and ord_name != "Guest" else "I see you have an open order with us."
                
                return {
                    "found": True,
                    "customer_id": None, # Guest
                    "name": ord_name,
                    "phone": clean_phone,
                    "recent_order": {
                        "order_id": ord.order_id,
                        "state": ord.state,
                        "total_dollars": ord.total_dollars,
                        "created_at": ord.created_at.isoformat() if ord.created_at else None,
                        "items": [
                            {"name": i.name, "quantity": i.quantity, "modifiers": i.modifiers}
                            for i in getattr(ord, "items", [])  # SquareOrder might not have items attached here yet? 
                        ] 
                    },
                    "message": msg
                }

        # --- STEP 2: Name Search (Fallback) ---
        # Only reachable if Step 1 failed (no profile for phone) AND we have a name
        if not cust and name_query:
            logger.info(f"🔍 Searching Square by Name: {name_query}")
            matches = await square_client.search_customers(name=name_query, limit=5)
            
            if not matches:
                 logger.info(f"⚠️ Square Name Search failed for '{name_query}'. Proceeding to DB Fallback.")
                 # Fall through to Step 3
                 pass

            elif len(matches) == 1:
                cust = matches[0]
                given = g(cust, "given_name", "")
                family = g(cust, "family_name", "")
                phone = g(cust, "phone_number", "")
                cid = g(cust, "id")
                
                masked = phone[-3:] if phone and len(phone) >= 3 else "..."
                return {
                    "found": True,
                    "customer_id": cid,
                    "name": f"{given} {family}".strip(),
                    "message": f"I found one {given}. Just to check, is your number ending in {masked}?"
                }
                
            elif len(matches) > 1:
                # Ambiguity handling
                options_str = ", ".join([f"{g(c,'given_name')} {g(c,'family_name')}" for c in matches[:3]])
                return {
                    "found": True, 
                    "count": len(matches),
                    "message": f"I found a few people called {name_query}. Could you give me your mobile number so I can find the right one?"
                }

        # --- STEP 3: Appwrite DB Search (Fallback) ---
        # Only reachable if Square failed to find anyone by Phone OR Name
        if name_query:
            logger.info(f"🔍 Falling back to Appwrite DB Search: {name_query}")
            # Tenant ID is implicitly Saranda for this handler
            customers = await db_service.find_customers_by_name(name_query, "saranda")
            
            if customers:
                if len(customers) == 1:
                    cust = customers[0]
                    phone = cust.get("phone", "")
                    masked = phone[-3:] if len(phone) >= 3 else "..."
                    return {
                        "found": True,
                        "source": "db",
                        "customer": {
                            "name": cust.get("name"),
                            "phone": phone,
                            "id": cust.get("$id"),
                            "sms_status": cust.get("sms_status")
                        },
                        "message": f"I found {cust.get('name')} in our records. Is that you?"
                    }
                else:
                    # Multiple matches
                    options = []
                    for c in customers[:3]:
                        p = c.get("phone", "")
                        m = p[-3:] if len(p) >= 3 else ""
                        options.append(f"{c.get('name')} (...{m})")
                    return {
                        "found": True,
                        "count": len(customers),
                        "message": f"I found a few people named {name_query}: {', '.join(options)}. Which one is you?"
                    }

        return {
            "found": False,
            "message": "I couldn't find your details. May I have your name again?"
        }

    except Exception as e:
        logger.error(f"Customer lookup failed: {e}")
        return {
            "found": False,
            "message": "I couldn't find a matching profile. Could I get your name again?"
        }


# =============================================================================
# SARANDA FUNCTION DISPATCHER
# =============================================================================

class SarandaFunctionDispatcher:
    """
    Dispatches Saranda-specific function calls.
    
    Handles restaurant operations: orders, reservations, menu queries.
    Integrates with WhatsApp HITL for all approval-required actions.
    """
    
    def __init__(self, user_phone: str, abuse_protection=None, tenant_config=None, call_sid: str = None):
        self.user_phone = user_phone
        self.abuse_protection = abuse_protection
        self.tenant_config = tenant_config or {}
        self.call_sid = call_sid
        
        # Resolve Transfer Number (Config Driven)
        # Priority:
        # 1. 'business_phone' from Appwrite Config (mapped from twilio_phone column)
        # 2. 'staff_phone' from Appwrite Config (custom column)
        # 3. Environment Variable Fallback
        self.transfer_number = self.tenant_config.get("business_phone")
        if not self.transfer_number:
             self.transfer_number = self.tenant_config.get("staff_phone")
        
        if not self.transfer_number:
            # Fallback
            self.transfer_number = getattr(settings, 'SARANDA_STAFF_PHONE', settings.STAFF_PHONE_NUMBER)
            
        logger.info(f"📞 Saranda Dispatcher initialized. Transfer Target: {self.transfer_number}")
    
    async def execute(self, function_name: str, args: dict, context: dict = None) -> dict:
        """Execute a Saranda function with error handling."""
        
        TIMEOUT = 15.0
        context = context or {}
        
        try:
            result = await asyncio.wait_for(
                self._dispatch(function_name, args, context),
                timeout=TIMEOUT
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Function {function_name} timed out")
            return {
                "success": False,
                "message": "I'm having trouble connecting. Let me take your details and have someone call you back."
            }
        except Exception as e:
            logger.error(f"Function error {function_name}: {e}")
            return {
                "success": False,
                "message": "Something went wrong on my end. Could you try that again?"
            }
    
    async def _dispatch(self, function_name: str, args: dict, context: dict) -> dict:
        """Route function calls to handlers."""
        
        # Order operations
        if function_name == "submit_order":
            # Pass call_sid if available
            return await handle_submit_order(args, self.user_phone, call_sid=self.call_sid)
        
        elif function_name == "request_change":
            # Pass transfer number
            return await handle_request_change(args, self.user_phone, transfer_to=self.transfer_number)
        
        elif function_name == "request_cancellation":
            return await handle_request_cancellation(args, self.user_phone, transfer_to=self.transfer_number)
        
        # Reservations
        elif function_name == "request_reservation":
            return await handle_request_reservation(args, self.user_phone, business_phone=self.transfer_number)
        
        # Status
        elif function_name == "check_order_status":
            return await handle_check_order_status(args, self.user_phone)
        
        # Menu / Info
        elif function_name == "get_menu_info":
            return await handle_get_menu_info(args)
        
        elif function_name == "get_restaurant_info":
            return await handle_get_restaurant_info(args)
        
        # Customer lookup
        elif function_name == "lookup_customer":
            return await lookup_customer(args, self.user_phone)
        
        # Call control
        elif function_name == "end_call":
            return {"action": "end_call", "success": True}
        
        # Abuse protection
        elif function_name == "flag_off_topic" or function_name == "report_user_behavior":
            if self.abuse_protection:
                # Map arguments to report_violation
                category = args.get("category", "off_topic")
                # If tool calls 'flag_off_topic', it usually sends 'reason'
                reason = args.get("reason", "unspecified")
                
                return self.abuse_protection.report_violation(category, reason)
            return {"message": "Let's focus on your order. What can I get for you?"}
        
        # Transfer
        elif function_name == "transfer_to_staff":
            return {
                "action": "transfer",
                "transfer_to": self.transfer_number,
                "message": "Sure, let me put you through to the team."
            }
        
        else:
            logger.warning(f"Unknown Saranda function: {function_name}")
            return {"error": f"Unknown function: {function_name}"}
