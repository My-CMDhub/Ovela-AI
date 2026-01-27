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
from typing import Dict, Any, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
from core.config import settings




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

async def handle_submit_order(args: dict, user_phone: str) -> dict:
    """
    Submit a new pickup order for kitchen approval via Square.
    
    Creates an order in Square (OPEN state) and tracks it for HITL approval.
    """
    
    # Get current time in Perth timezone
    tz = ZoneInfo("Australia/Perth")
    now = datetime.now(tz)
    current_day = now.strftime("%A")  # e.g., "Monday"
    current_time = now.strftime("%I:%M %p")  # e.g., "7:30 PM"
    
    # === VALIDATION: Check if we can accept orders ===
    
    # Check if restaurant is open
    is_open, rejection_reason = is_within_operating_hours(current_day, current_time)
    if not is_open:
        next_open = get_next_opening_datetime()
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
            price_cents = int(price_inc_mods * 100)
            
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
    
    # --- SQUARE INTEGRATION ---
    call_id = generate_request_id() # Using existing generator for short ID as call_id suffix
    
    try:
        square_client = SquareClient()
        order = await square_client.create_pickup_order(
            customer_name=customer_name,
            customer_phone=user_phone,
            items=square_items,
            pickup_time=pickup_time,
            call_id=call_id
        )
        
        # Format summary
        items_summary = ", ".join([f"{item.quantity}x {item.name}" for item in square_items])
        
        # Track for HITL
        request = SquareOrderRequest(
            square_order_id=order.order_id,
            square_order_version=order.version,
            call_id=call_id,
            request_id=call_id,
            customer_name=customer_name,
            customer_phone=user_phone,
            pickup_time=pickup_time,
            total_cents=int(order.total_cents),
            items_summary=items_summary
        )
        saranda_approval_tracker.track(request)
        
        return {
            "success": True,
            "request_id": call_id,
            "status": "pending_approval",
            "total_amount": order.total_dollars,
            "estimated_pickup": pickup_time,
            "message": f"I've sent that through to the kitchen. {len(square_items)} item{'s' if len(square_items) > 1 else ''} totalling ${order.total_dollars:.2f}. They'll confirm shortly and you'll get a text. Pickup in about {pickup_time}."
        }
        
    except Exception as e:
        logger.error(f"Failed to create Square order: {e}")
        return {
            "success": False,
            "message": "I'm having a bit of trouble connecting to the kitchen system properly. Could you give us a call directly?"
        }


async def handle_request_change(args: dict, user_phone: str) -> dict:
    """
    Request a change to an existing order via HITL.
    
    Args:
        args: {
            order_id?: str,  # If known
            change_type: str,  # "add_item", "remove_item", "modify", "change_time"
            details: str  # Description of change
        }
    """
    order_id = args.get("order_id", "")
    change_type = args.get("change_type", "modify")
    details = args.get("details", "")
    customer_name = args.get("customer_name", "")
    
    if not details:
        return {
            "success": False,
            "message": "What would you like to change about your order?"
        }
    
    # Try to find order by phone if no ID provided
    if not order_id:
        # Look for most recent order from this phone
        for req_id, req in saranda_queue._completed.items():
            if hasattr(req, 'customer_phone') and req.customer_phone == user_phone:
                if req.status == RequestStatus.APPROVED:
                    order_id = req_id
                    customer_name = customer_name or req.customer_name
                    break
    
    if not order_id:
        return {
            "success": False,
            "message": "I couldn't find your recent order. Do you have an order number, or can you tell me what name it's under?"
        }
    
    # Create change request
    request_id = generate_request_id()
    change_order = OrderRequest(
        id=request_id,
        customer_name=customer_name,
        customer_phone=user_phone,
        items=[],  # Changes don't have items
        pickup_time="",
        request_type=RequestType.CHANGE_REQUEST,
        original_order_id=order_id,
        change_details=details
    )
    
    # Add to queue
    await saranda_queue.add(change_order)
    
    # Send WhatsApp if active
    if saranda_queue.get_active() and saranda_queue.get_active().id == request_id:
        try:
            await staff_notification_service.send_whatsapp_order_approval(
                request_id=request_id,
                request_type="change",
                customer_name=customer_name,
                order_summary=f"Change to #{order_id}: {details}",
                pickup_time="",
                total_amount=0
            )
        except Exception as e:
            logger.error(f"Failed to send change WhatsApp: {e}")
    
    return {
        "success": True,
        "request_id": request_id,
        "original_order_id": order_id,
        "status": "pending_approval",
        "message": f"I've sent that change request to the kitchen. They'll let me know if they can do that. You'll get a text confirming."
    }


async def handle_request_cancellation(args: dict, user_phone: str) -> dict:
    """
    Request to cancel an order via HITL.
    Kitchen needs to confirm they haven't started cooking.
    """
    order_id = args.get("order_id", "")
    reason = args.get("reason", "Customer requested")
    customer_name = args.get("customer_name", "")
    
    if not order_id:
        return {
            "success": False,
            "message": "Do you have your order number so I can check with the kitchen?"
        }
    
    # Create cancellation request
    request_id = generate_request_id()
    cancel_request = OrderRequest(
        id=request_id,
        customer_name=customer_name,
        customer_phone=user_phone,
        items=[],
        pickup_time="",
        request_type=RequestType.CANCELLATION,
        original_order_id=order_id,
        change_details=reason
    )
    
    await saranda_queue.add(cancel_request)
    
    # Send WhatsApp
    if saranda_queue.get_active() and saranda_queue.get_active().id == request_id:
        try:
            await staff_notification_service.send_whatsapp_order_approval(
                request_id=request_id,
                request_type="cancel",
                customer_name=customer_name,
                order_summary=f"CANCEL #{order_id}: {reason}",
                pickup_time="",
                total_amount=0
            )
        except Exception as e:
            logger.error(f"Failed to send cancel WhatsApp: {e}")
    
    return {
        "success": True,
        "request_id": request_id,
        "status": "pending_approval",
        "message": "Let me check if the kitchen has started on that yet. I'll text you to confirm the cancellation."
    }


# =============================================================================
# RESERVATION HANDLERS
# =============================================================================

async def handle_request_reservation(args: dict, user_phone: str) -> dict:
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
        return {
            "success": False,
            "message": f"For groups larger than {max_group}, please call us directly on (08) 6401 6397 so we can work something out."
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
    tz = ZoneInfo("Australia/Perth")
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
        try:
            await staff_notification_service.send_whatsapp_order_approval(
                request_id=request_id,
                request_type="reservation",
                customer_name=customer_name,
                order_summary=summary,
                pickup_time=time,
                total_amount=0
            )
        except Exception as e:
            logger.error(f"Failed to send reservation WhatsApp: {e}")
    
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
        hours = info["hours"]
        return {
            "hours": hours,
            "message": "We're open Tuesday to Friday from 4:30 to 9pm, and Saturday and Sunday we're open 11:30am to 2pm for lunch, and 4:30 to 9pm for dinner. Closed Mondays."
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
        "address": info["address"],
        "phone": info["phone"],
        "message": f"Saranda Cafe and Pizzeria, we're at {info['address']}. Phone is {info['phone']}. Pickup only from the restaurant, pay when you collect."
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
    
    def __init__(self, user_phone: str, abuse_protection=None):
        self.user_phone = user_phone
        self.abuse_protection = abuse_protection
    
    async def execute(self, function_name: str, args: dict) -> dict:
        """Execute a Saranda function with error handling."""
        
        TIMEOUT = 15.0
        
        try:
            result = await asyncio.wait_for(
                self._dispatch(function_name, args),
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
    
    async def _dispatch(self, function_name: str, args: dict) -> dict:
        """Route function calls to handlers."""
        
        # Order operations
        if function_name == "submit_order":
            return await handle_submit_order(args, self.user_phone)
        
        elif function_name == "request_change":
            return await handle_request_change(args, self.user_phone)
        
        elif function_name == "request_cancellation":
            return await handle_request_cancellation(args, self.user_phone)
        
        # Reservations
        elif function_name == "request_reservation":
            return await handle_request_reservation(args, self.user_phone)
        
        # Menu / Info
        elif function_name == "get_menu_info":
            return await handle_get_menu_info(args)
        
        elif function_name == "get_restaurant_info":
            return await handle_get_restaurant_info(args)
        
        # Call control
        elif function_name == "end_call":
            return {"action": "end_call", "success": True}
        
        # Abuse protection
        elif function_name == "flag_off_topic":
            if self.abuse_protection:
                reason = args.get("reason", "unspecified")
                return self.abuse_protection.flag_off_topic(reason)
            return {"message": "Let's focus on your order. What can I get for you?"}
        
        # Transfer
        elif function_name == "transfer_to_staff":
            return {
                "action": "transfer",
                "transfer_to": getattr(settings, 'SARANDA_STAFF_PHONE', settings.STAFF_PHONE_NUMBER),
                "message": "Sure, let me put you through to the team."
            }
        
        else:
            logger.warning(f"Unknown Saranda function: {function_name}")
            return {"error": f"Unknown function: {function_name}"}
