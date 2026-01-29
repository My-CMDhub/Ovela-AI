"""
AI Tool Handlers
Executes tool calls from OpenAI function calling and returns results.
Each tool handler processes its specific action and interacts with services.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import logging

from services.appwrite import db_service
from services.email import email_service
from services.customers import customer_service
from services.bookings import booking_service

logger = logging.getLogger(__name__)
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")


async def execute_tool(tool_name: str, tool_args: dict, customer_id: str = None, whatsapp_id: str = None, tenant_id: str = None) -> str:
    """Execute a tool call and return the result as a string."""
    logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
    
    if tool_name == "check_availability":
        return await _handle_check_availability(tool_args, tenant_id)
    
    elif tool_name == "submit_booking_request":
        return await _handle_submit_booking_request(tool_args, whatsapp_id, tenant_id)
    
    elif tool_name == "get_my_bookings":
        return await _handle_get_my_bookings(whatsapp_id)
    
    elif tool_name == "submit_reschedule_request":
        return await _handle_submit_reschedule_request(tool_args, whatsapp_id)
    
    elif tool_name == "cancel_appointment":
        return await _handle_cancel_appointment(tool_args, whatsapp_id)
    
    elif tool_name == "report_violation":
        return await _handle_report_violation(tool_args, customer_id)
    
    elif tool_name == "request_human_callback":
        return await _handle_request_human_callback(tool_args, whatsapp_id)
    
    return json.dumps({"error": f"Unknown tool: {tool_name}"})


# ============ TOOL HANDLERS ============

async def _handle_check_availability(tool_args: dict, tenant_id: str = None) -> str:
    """Check available appointment slots for a specific date."""
    date_str = tool_args.get("date")
    
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except:
        return json.dumps({"available": False, "error": "Invalid date format. Use YYYY-MM-DD."})
    
    available_slots = db_service.get_availability(
        date=date_str,
        start_hour=9,
        end_hour=18,
        slot_duration=60,
        tenant_id=tenant_id
    )
    
    if available_slots:
        formatted_slots = []
        for slot in available_slots[:10]:
            try:
                slot_dt = datetime.strptime(f"{date_str} {slot}", "%Y-%m-%d %H:%M")
                formatted_slots.append({"time": slot, "display": slot_dt.strftime("%I:%M %p")})
            except:
                formatted_slots.append({"time": slot, "display": slot})
        
        return json.dumps({
            "available": True,
            "date": date_str,
            "slots": formatted_slots,
            "message": f"Found {len(formatted_slots)} available slots."
        })
    
    return json.dumps({"available": False, "date": date_str, "message": "No slots available on this date."})


async def _handle_submit_booking_request(tool_args: dict, whatsapp_id: str, tenant_id: str = None) -> str:
    """Create a pending booking request for owner approval."""
    customer_name = tool_args.get("customer_name")
    customer_email = tool_args.get("customer_email")
    service_name = tool_args.get("service_name", "Appointment")
    preferred_date = tool_args.get("preferred_date")
    preferred_time = tool_args.get("preferred_time")
    notes = tool_args.get("notes", "")
    
    if not customer_name:
        return json.dumps({"submitted": False, "error": "Customer name is required."})
    
    request_data = {
        "business_id": tenant_id or "default_business",
        "customer_name": customer_name,
        "customer_phone": whatsapp_id or "unknown",
        "customer_email": customer_email,
        "service_name": service_name,
        "preferred_date": preferred_date,
        "preferred_time": preferred_time,
        "notes": notes,
        "status": "pending",
        "source": "whatsapp",
        "created_at": datetime.now(MELBOURNE_TZ).isoformat()
    }
    
    result = db_service.create_booking_request(request_data)
    
    if result:
        request_id = result.get("$id")
        
        # Track customer stats
        db_service.update_customer_stats(whatsapp_id, "booking_request", {
            "customer_name": customer_name,
            "customer_email": customer_email,
            "service_name": service_name,
            "status": "pending"
        })
        
        # Notify owner
        try:
            business_settings = db_service.get_all_settings()
            owner_email = business_settings.get("owner_email") if business_settings else None
            business_name = business_settings.get("business_name", "Your Business") if business_settings else "Your Business"
            
            if owner_email:
                await email_service.send_owner_notification(
                    owner_email=owner_email,
                    customer_phone=whatsapp_id or "Unknown",
                    business_name=business_name,
                    source=f"Booking Request: {customer_name} wants {service_name} on {preferred_date} at {preferred_time}"
                )
        except Exception as e:
            logger.error(f"Failed to notify owner: {e}")
        
        return json.dumps({
            "submitted": True,
            "request_id": request_id,
            "message": "Your booking request has been submitted! The team will review and confirm shortly."
        })
    
    return json.dumps({"submitted": False, "error": "Failed to submit request. Please try again."})


async def _handle_get_my_bookings(whatsapp_id: str) -> str:
    """Get customer's current bookings."""
    if not whatsapp_id:
        return json.dumps({"found": False, "message": "Unable to identify customer."})
    
    bookings = booking_service.get_customer_bookings(whatsapp_id, status="confirmed")
    
    if bookings:
        formatted_lines = []
        raw_list = []
        
        for b in bookings:
            booking_id = b.get("$id")
            date = b.get("booking_date", "Unknown")
            time = b.get("booking_time", "")
            service = b.get("service_name", "Appointment")
            
            try:
                dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
                readable = dt.strftime("%A %d %B at %I:%M %p")
            except:
                readable = f"{date} {time}"
            
            formatted_lines.append(f"• {service} - {readable} (ID: {booking_id})")
            raw_list.append({
                "booking_id": booking_id,
                "date": date,
                "time": time,
                "readable_time": readable,
                "service": service
            })
        
        return json.dumps({
            "found": True,
            "count": len(bookings),
            "bookings": "Your upcoming bookings:\n" + "\n".join(formatted_lines),
            "raw_bookings": raw_list,
            "instructions": "Use the booking ID to reschedule or cancel."
        })
    
    return json.dumps({"found": False, "message": "No upcoming bookings found."})


async def _handle_submit_reschedule_request(tool_args: dict, whatsapp_id: str) -> str:
    """Create a reschedule request for owner approval."""
    booking_id = tool_args.get("booking_id")
    new_date = tool_args.get("new_date")
    new_time = tool_args.get("new_time")
    reason = tool_args.get("reason", "")
    
    if not booking_id:
        return json.dumps({"submitted": False, "error": "Missing booking_id. Call get_my_bookings first."})
    
    if not new_date or not new_time:
        return json.dumps({"submitted": False, "error": "Both new_date and new_time are required."})
    
    # Rate limiting
    if whatsapp_id:
        allowed, msg = booking_service.check_rate_limit(whatsapp_id, 'reschedule')
        if not allowed:
            return json.dumps({"submitted": False, "error": msg})
    
    # Get original booking
    original_booking = db_service._make_request(
        "GET",
        f"/databases/ovela_db/collections/bookings/documents/{booking_id}"
    )
    
    if not original_booking:
        return json.dumps({"submitted": False, "error": "Original booking not found."})
    
    customer_name = original_booking.get("customer_name", "Customer")
    customer_email = original_booking.get("customer_email")
    service_name = original_booking.get("service_name", "Appointment")
    
    request_data = {
        "business_id": "default_business",
        "customer_name": customer_name,
        "customer_phone": whatsapp_id or "unknown",
        "customer_email": customer_email,
        "service_name": f"Reschedule: {service_name}",
        "preferred_date": new_date,
        "preferred_time": new_time,
        "notes": f"Reschedule from booking {booking_id}. Reason: {reason}" if reason else f"Reschedule from booking {booking_id}",
        "status": "pending",
        "source": "reschedule",
        "original_booking_id": booking_id,
        "created_at": datetime.now(MELBOURNE_TZ).isoformat()
    }
    
    result = db_service.create_booking_request(request_data)
    
    if result:
        request_id = result.get("$id")
        
        # Notify owner
        try:
            business_settings = db_service.get_all_settings()
            owner_email = business_settings.get("owner_email") if business_settings else None
            business_name = business_settings.get("business_name", "Your Business") if business_settings else "Your Business"
            
            if owner_email:
                await email_service.send_owner_notification(
                    owner_email=owner_email,
                    customer_phone=whatsapp_id or "Unknown",
                    business_name=business_name,
                    source=f"Reschedule Request: {customer_name} wants to move {service_name} to {new_date} at {new_time}"
                )
        except Exception as e:
            logger.error(f"Failed to notify owner: {e}")
        
        return json.dumps({
            "submitted": True,
            "request_id": request_id,
            "message": "Your reschedule request has been submitted! The team will confirm shortly."
        })
    
    return json.dumps({"submitted": False, "error": "Failed to submit request. Please try again."})


async def _handle_cancel_appointment(tool_args: dict, whatsapp_id: str) -> str:
    """Cancel an existing appointment."""
    booking_id = tool_args.get("booking_id")
    reason = tool_args.get("reason", "Customer requested")
    
    if not booking_id:
        return json.dumps({"cancelled": False, "error": "Missing booking_id. Call get_my_bookings first."})
    
    # Rate limiting
    if whatsapp_id:
        allowed, msg = booking_service.check_rate_limit(whatsapp_id, 'cancel')
        if not allowed:
            return json.dumps({"cancelled": False, "error": msg})
    
    result = db_service.update_booking(booking_id, {"status": "cancelled", "notes": reason})
    
    if result:
        customer_email = result.get("customer_email")
        customer_name = result.get("customer_name", "there")
        service_name = result.get("service_name", "Appointment")
        booking_date = result.get("booking_date", "")
        booking_time = result.get("booking_time", "")
        
        # Get business settings
        business_settings = db_service.get_all_settings()
        business_name = (business_settings.get("business_name") if business_settings else None) or "Your Business"
        owner_email = business_settings.get("owner_email") if business_settings else None
        
        # Track stats
        db_service.update_customer_stats(whatsapp_id, "cancel", {
            "service_name": service_name,
            "status": "cancelled"
        })
        
        # Email customer (white-label)
        if customer_email:
            try:
                await email_service.send_cancellation_confirmation(
                    email=customer_email,
                    booking_id=booking_id,
                    name=customer_name,
                    business_name=business_name
                )
            except Exception as e:
                logger.error(f"Failed to send cancellation email: {e}")
        
        # Notify owner
        if owner_email:
            try:
                await email_service.send_owner_cancellation_notification(
                    owner_email=owner_email,
                    customer_name=customer_name,
                    customer_phone=whatsapp_id or "Unknown",
                    service_name=service_name,
                    booking_date=booking_date,
                    booking_time=booking_time
                )
            except Exception as e:
                logger.error(f"Failed to notify owner about cancellation: {e}")
        
        return json.dumps({
            "cancelled": True,
            "message": "Appointment cancelled. Confirmation email sent."
        })
    
    return json.dumps({"cancelled": False, "error": "Failed to cancel booking. It may not exist."})


async def _handle_report_violation(tool_args: dict, customer_id: str) -> str:
    """Report a user for abuse."""
    reason = tool_args.get("reason")
    
    if customer_id:
        try:
            cust = customer_service._make_request(
                "GET",
                f"/databases/ovela_db/collections/customers/documents/{customer_id}"
            )
            if cust:
                current_count = cust.get("violation_count", 0)
                is_locked = customer_service.report_violation(customer_id, current_count)
                msg = "Violation logged."
                if is_locked:
                    msg += " User is now in cooldown mode."
                return json.dumps({"violation_reported": True, "message": msg})
        except Exception as e:
            logger.error(f"Error logging violation: {e}")
    
    return json.dumps({"violation_reported": True, "message": "Violation logged."})


# In-memory store for callback request cooldowns (in production, use Redis or DB)
_callback_cooldowns = {}

async def _handle_request_human_callback(tool_args: dict, whatsapp_id: str) -> str:
    """Handle customer request to speak to a human. Sends email notification with 30-min cooldown."""
    reason = tool_args.get("reason", "Customer prefers human support")
    urgency = tool_args.get("urgency", "medium")
    
    if not whatsapp_id:
        return json.dumps({
            "notified": False,
            "error": "Unable to identify customer."
        })
    
    # Check 30-minute cooldown
    now = datetime.now(MELBOURNE_TZ)
    last_request_time = _callback_cooldowns.get(whatsapp_id)
    
    if last_request_time:
        time_since_last = (now - last_request_time).total_seconds()
        cooldown_seconds = 30 * 60  # 30 minutes
        
        if time_since_last < cooldown_seconds:
            remaining_minutes = int((cooldown_seconds - time_since_last) / 60)
            return json.dumps({
                "notified": False,
                "already_requested": True,
                "remaining_minutes": remaining_minutes,
                "message": f"I've already notified the team about your callback request. They should call you within 30 minutes. If you haven't heard back after 30 minutes, let me know and I'll send another notification. You can also try calling them directly."
            })
    
    # Get business settings
    business_settings = db_service.get_all_settings()
    owner_email = business_settings.get("owner_email") if business_settings else None
    business_name = (business_settings.get("business_name") if business_settings else None) or "Your Business"
    business_phone = business_settings.get("business_phone") if business_settings else None
    
    if not owner_email:
        # No owner email configured - provide alternative
        if business_phone:
            return json.dumps({
                "notified": False,
                "no_email_configured": True,
                "business_phone": business_phone,
                "message": f"I'm unable to send a notification right now, but you can call {business_name} directly at {business_phone}."
            })
        return json.dumps({
            "notified": False,
            "error": "Unable to send notification. Please try calling the business directly."
        })
    
    # Get customer name from database
    customer_name = "Customer"
    try:
        customer = db_service._make_request(
            "GET",
            f"/databases/ovela_db/collections/customers/documents",
            # FIX: Use string format directly
            params={"queries": [f'equal("whatsapp_id", "{whatsapp_id}")']}
        )
        if customer and customer.get("documents"):
            customer_name = customer["documents"][0].get("name", "Customer")
    except Exception as e:
        logger.error(f"Error fetching customer name: {e}")
    
    # Send email notification
    try:
        await email_service.send_human_callback_request(
            owner_email=owner_email,
            customer_name=customer_name,
            customer_phone=whatsapp_id,
            reason=reason,
            urgency=urgency,
            business_phone=business_phone
        )
        
        # Record the request time for cooldown
        _callback_cooldowns[whatsapp_id] = now
        
        logger.info(f"Callback request sent for {whatsapp_id}: {reason}")
        
        response_data = {
            "notified": True,
            "message": f"I've notified the {business_name} team about your request. Someone will call you back within 30 minutes."
        }
        
        # Add business phone for reference
        if business_phone:
            response_data["business_phone"] = business_phone
            response_data["message"] += f" If you need to reach them urgently, you can also call directly at {business_phone}."
        
        return json.dumps(response_data)
        
    except Exception as e:
        logger.error(f"Failed to send callback notification: {e}")
        return json.dumps({
            "notified": False,
            "error": "Failed to send notification. Please try again or call the business directly."
        })

