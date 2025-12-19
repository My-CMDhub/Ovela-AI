"""
Dashboard API Routes
Provides endpoints for the business owner dashboard to fetch data.
"""
from fastapi import APIRouter, HTTPException, Depends
from services.appwrite import db_service
from services.email import email_service
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from core.config import settings
from core.security import verify_dashboard_access
from rules.whitelist import is_whitelisted
import logging

router = APIRouter(dependencies=[Depends(verify_dashboard_access)])
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
logger = logging.getLogger(__name__)


# ============ CONVERSATIONS ============

@router.get("/conversations")
async def get_conversations(status: str = None, limit: int = 100):
    """
    Get conversations, optionally filtered by status.
    status: active, archived (or None for all)
    """
    try:
        # Build query parameters
        params = {"limit": limit, "orderDesc": "$updatedAt"}
        
        if status:
            params["queries"] = [f'equal("status", "{status}")']
        
        result = db_service._make_request(
            "GET",
            f"/databases/{db_service.db_id}/collections/conversations/documents",
            params=params
        )
        
        conversations = result.get("documents", []) if result else []
        total = result.get("total", 0) if result else 0
        
        return {
            "success": True,
            "conversations": conversations,
            "total": total
        }
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        return {"success": False, "conversations": [], "total": 0}


@router.get("/conversations/recent")
async def get_recent_conversations(limit: int = 5):
    """Get recent conversations for activity feed."""
    try:
        result = db_service._make_request(
            "GET",
            f"/databases/{db_service.db_id}/collections/conversations/documents",
            params={"limit": limit, "orderDesc": "$updatedAt"}
        )
        
        conversations = result.get("documents", []) if result else []
        
        return {
            "success": True,
            "conversations": conversations
        }
    except Exception as e:
        logger.error(f"Error fetching recent conversations: {e}")
        return {"success": False, "conversations": []}


@router.get("/conversations/active-count")
async def get_active_conversations_count():
    """Get count of active conversations."""
    try:
        result = db_service._make_request(
            "GET",
            f"/databases/{db_service.db_id}/collections/conversations/documents",
            params={"limit": 1, "queries": ['equal("status", "active")']}
        )
        
        total = result.get("total", 0) if result else 0
        
        return {"count": total}
    except Exception as e:
        logger.error(f"Error fetching active conversations count: {e}")
        return {"count": 0}


# ============ CUSTOMERS ============

@router.get("/customers")
async def get_customers(limit: int = 100):
    """Get all customers."""
    try:
        result = db_service._make_request(
            "GET",
            f"/databases/{db_service.db_id}/collections/customers/documents",
            params={"limit": limit, "orderDesc": "$createdAt"}
        )
        
        customers = result.get("documents", []) if result else []
        total = result.get("total", 0) if result else 0
        
        return {
            "success": True,
            "customers": customers,
            "total": total
        }
    except Exception as e:
        logger.error(f"Error fetching customers: {e}")
        return {"success": False, "customers": [], "total": 0}


@router.get("/customers/count")
async def get_customers_count():
    """Get total customer count."""
    try:
        result = db_service._make_request(
            "GET",
            f"/databases/{db_service.db_id}/collections/customers/documents",
            params={"limit": 1}
        )
        
        total = result.get("total", 0) if result else 0
        
        return {"count": total}
    except Exception as e:
        logger.error(f"Error fetching customers count: {e}")
        return {"count": 0}


# ============ BOOKINGS (Native System - replaces Cal.com) ============

class BookingPayload(BaseModel):
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    service_name: str
    booking_date: str  # YYYY-MM-DD
    booking_time: str  # HH:MM
    duration_minutes: Optional[int] = 30
    notes: Optional[str] = ""
    source: Optional[str] = "dashboard"


@router.get("/bookings")
async def get_bookings(date: str = None, status: str = "confirmed"):
    """
    Get bookings from native database.
    date: YYYY-MM-DD (optional, defaults to all)
    status: confirmed, completed, cancelled, no-show
    """
    try:
        bookings = db_service.get_bookings(date=date, status=status)
        
        # Sort by date and time
        bookings.sort(key=lambda x: (x.get("booking_date", ""), x.get("booking_time", "")))
        
        return {
            "success": True,
            "bookings": bookings,
            "count": len(bookings)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bookings/today")
async def get_today_bookings():
    """Get today's confirmed bookings."""
    try:
        today = datetime.now(MELBOURNE_TZ).strftime("%Y-%m-%d")
        bookings = db_service.get_bookings(date=today, status="confirmed")
        
        # Sort by time
        bookings.sort(key=lambda x: x.get("booking_time", ""))
        
        return {
            "success": True,
            "bookings": bookings,
            "count": len(bookings),
            "date": today
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bookings")
async def create_booking(payload: BookingPayload):
    """Create a new confirmed booking."""
    try:
        booking_data = {
            "customer_name": payload.customer_name,
            "customer_phone": payload.customer_phone,
            "customer_email": payload.customer_email,
            "service_name": payload.service_name,
            "booking_date": payload.booking_date,
            "booking_time": payload.booking_time,
            "duration_minutes": payload.duration_minutes,
            "notes": payload.notes,
            "source": payload.source,
            "status": "confirmed"
        }
        
        result = db_service.create_booking(booking_data)
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create booking")
        
        # Send confirmation email if email provided
        if payload.customer_email:
            await email_service.send_booking_confirmation(
                name=payload.customer_name,
                email=payload.customer_email,
                date=payload.booking_date,
                time=payload.booking_time,
                service=payload.service_name
            )
        
        return {"success": True, "booking": result, "message": "Booking created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/bookings/{booking_id}")
async def update_booking(booking_id: str, status: str = None, booking_date: str = None, booking_time: str = None, notes: str = None):
    """Update a booking (reschedule, cancel, complete)."""
    try:
        update_data = {}
        if status:
            update_data["status"] = status
        if booking_date:
            update_data["booking_date"] = booking_date
        if booking_time:
            update_data["booking_time"] = booking_time
        if notes:
            update_data["notes"] = notes
        
        result = db_service.update_booking(booking_id, update_data)
        
        if not result:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        return {"success": True, "booking": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/availability")
async def get_availability(date: str):
    """
    Get available time slots for a specific date.
    date: YYYY-MM-DD format
    """
    try:
        # Validate date format
        datetime.strptime(date, "%Y-%m-%d")
        
        # Get settings for business hours (or use defaults)
        settings_data = db_service.get_all_settings()
        
        # Default: 9am-6pm, 30 min slots
        start_hour = 9
        end_hour = 18
        slot_duration = 30
        
        # Parse business hours from settings if available
        if settings_data and settings_data.get("business_hours"):
            # Simple parsing: "9:00 AM - 6:00 PM"
            hours = settings_data.get("business_hours", "")
            # For now, use defaults. Can enhance parsing later.
        
        available_slots = db_service.get_availability(
            date=date,
            start_hour=start_hour,
            end_hour=end_hour,
            slot_duration=slot_duration
        )
        
        return {
            "success": True,
            "date": date,
            "slots": available_slots,
            "slot_count": len(available_slots)
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_dashboard_stats():
    """Get dashboard statistics from native database."""
    try:
        today = datetime.now(MELBOURNE_TZ).strftime("%Y-%m-%d")
        
        # Today's bookings
        today_bookings = db_service.get_bookings(date=today, status="confirmed")
        
        # All upcoming (confirmed) bookings
        upcoming_bookings = db_service.get_bookings(status="confirmed")
        
        # Pending requests count
        pending_requests = db_service.get_booking_requests(status="pending")
        
        return {
            "success": True,
            "today_appointments": len(today_bookings),
            "upcoming_appointments": len(upcoming_bookings),
            "pending_requests": len(pending_requests),
            "source": "native"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================
# SETTINGS ENDPOINTS
# =====================

from pydantic import BaseModel
from typing import Optional

class BusinessSettingsPayload(BaseModel):
    business_name: Optional[str] = ""
    industry: Optional[str] = "beauty"
    business_hours: Optional[str] = ""
    services: Optional[str] = ""
    location: Optional[str] = ""
    phone: Optional[str] = ""
    owner_email: Optional[str] = ""  # Email for notifications
    business_phone: Optional[str] = ""  # Phone shown to customers
    custom_instructions: Optional[str] = ""
    current_promotions: Optional[str] = ""
    ai_tone: Optional[str] = "friendly"


# For MVP, use a hardcoded business ID. In production, this comes from auth.
DEFAULT_BUSINESS_ID = "default_business"


@router.get("/settings")
async def get_settings():
    """
    Get business settings from Appwrite.
    """
    try:
        # Try to get existing business document
        business = db_service.get_business_by_id(DEFAULT_BUSINESS_ID)
        
        if business:
            # Parse stored JSON settings from system_prompt_override field
            import json
            settings_json = business.get("system_prompt_override", "{}")
            try:
                settings_data = json.loads(settings_json)
            except json.JSONDecodeError:
                settings_data = {}
            
            return {
                "success": True,
                "settings": {
                    "business_name": business.get("name", ""),
                    "industry": business.get("industry", "beauty"),
                    "business_hours": settings_data.get("business_hours", ""),
                    "services": settings_data.get("services", ""),
                    "location": settings_data.get("location", ""),
                    "phone": settings_data.get("phone", ""),
                    "owner_email": settings_data.get("owner_email", ""),
                    "business_phone": settings_data.get("business_phone", ""),
                    "custom_instructions": settings_data.get("custom_instructions", ""),
                    "current_promotions": settings_data.get("current_promotions", ""),
                    "ai_tone": settings_data.get("ai_tone", "friendly"),
                }
            }
        else:
            # Return defaults if no business exists yet
            return {
                "success": True,
                "settings": {
                    "business_name": "",
                    "industry": "beauty",
                    "business_hours": "",
                    "services": "",
                    "location": "",
                    "phone": "",
                    "owner_email": "",
                    "business_phone": "",
                    "custom_instructions": "",
                    "current_promotions": "",
                    "ai_tone": "friendly",
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings")
async def save_settings(payload: BusinessSettingsPayload):
    """
    Save business settings to Appwrite.
    """
    try:
        import json
        
        # Prepare settings JSON (everything except business_name and industry)
        settings_data = {
            "business_hours": payload.business_hours,
            "services": payload.services,
            "location": payload.location,
            "phone": payload.phone,
            "owner_email": payload.owner_email,
            "business_phone": payload.business_phone,
            "custom_instructions": payload.custom_instructions,
            "current_promotions": payload.current_promotions,
            "ai_tone": payload.ai_tone
        }
        
        # Try to update or create business (includes separate columns for key fields)
        result = db_service.upsert_business(
            business_id=DEFAULT_BUSINESS_ID,
            name=payload.business_name or "My Business",
            industry=payload.industry or "beauty",
            settings_json=json.dumps(settings_data),
            owner_email=payload.owner_email or "",
            business_phone=payload.business_phone or payload.phone or ""
        )
        
        if result:
            return {"success": True, "message": "Settings saved"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save settings")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/industry-lock")
async def get_industry_lock():
    """
    Check if the industry is locked for this business.
    Returns locked status and current industry.
    """
    try:
        business = db_service.get_business_by_id(DEFAULT_BUSINESS_ID)
        
        if not business:
            # No business yet, not locked
            return {
                "success": True,
                "locked": False,
                "industry": "beauty"
            }
        
        # Check if industry_locked is set in system_prompt_override
        import json
        settings_json = business.get("system_prompt_override", "{}")
        try:
            settings_data = json.loads(settings_json)
        except json.JSONDecodeError:
            settings_data = {}
        
        is_locked = settings_data.get("industry_locked", False)
        current_industry = business.get("industry", "beauty")
        
        return {
            "success": True,
            "locked": is_locked,
            "industry": current_industry
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ BOOKING REQUESTS (Appointment-Only Mode) ============

@router.get("/requests")
async def get_booking_requests(status: str = None):
    """
    Get booking requests, optionally filtered by status.
    status: pending, approved, rejected (or None for all)
    """
    try:
        requests = db_service.get_booking_requests(status=status)
        return {
            "success": True,
            "requests": requests,
            "count": len(requests)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/requests/pending-count")
async def get_pending_count():
    """Get count of pending requests for badge display."""
    try:
        requests = db_service.get_booking_requests(status="pending")
        return {"count": len(requests)}
    except Exception as e:
        return {"count": 0}


@router.patch("/requests/{request_id}/approve")
async def approve_request(request_id: str):
    """
    Approve a booking request:
    1. Update request status to "approved"
    2. Create a confirmed booking record in bookings collection
    3. Notify customer via WhatsApp
    4. Send confirmation email
    """
    from services.meta import meta_service
    
    try:
        # Update status
        result = db_service.update_booking_request(request_id, {"status": "approved"})
        
        if not result:
            raise HTTPException(status_code=404, detail="Request not found")
        
        # Get customer details
        customer_phone = result.get("customer_phone")
        customer_name = result.get("customer_name", "there")
        customer_email = result.get("customer_email")
        service = result.get("service_name", "Appointment")
        preferred_date = result.get("preferred_date", "TBD")
        preferred_time = result.get("preferred_time", "TBD")
        
        # Get business settings for dynamic info
        business_settings = db_service.get_all_settings()
        business_name = (business_settings.get("business_name") if business_settings else None) or "ibrow threading"
        business_phone = (business_settings.get("business_phone") if business_settings else None) or "0475 921 152"
        
        print(f"[DEBUG] customer_email: {customer_email}, business_phone: {business_phone}")
        
        # Check if this is a reschedule request
        is_reschedule = result.get("source") == "reschedule"
        original_booking_id = result.get("original_booking_id")
        
        if is_reschedule and original_booking_id:
            # UPDATE existing booking instead of creating new one
            update_data = {
                "booking_date": preferred_date,
                "booking_time": preferred_time,
                "status": "confirmed",
                "notes": f"Rescheduled from request {request_id}"
            }
            booking_result = db_service.update_booking(original_booking_id, update_data)
            
            if booking_result:
                print(f"[RESCHEDULE] Updated booking {original_booking_id} with new time")
        else:
            # Create NEW confirmed booking record
            booking_data = {
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "customer_email": customer_email,
                "service_name": service,
                "booking_date": preferred_date,
                "booking_time": preferred_time,
                "status": "confirmed",
                "source": "request_approval",
                "notes": f"Approved from request {request_id}",
                "created_at": datetime.now(MELBOURNE_TZ).isoformat()
            }
            booking_result = db_service.create_booking(booking_data)
            
            if booking_result:
                print(f"[BOOKING] Created confirmed booking {booking_result.get('$id')} from request {request_id}")
        
        # Send WhatsApp notification
        action_word = "rescheduled" if is_reschedule else "approved"
        if customer_phone:
            message = f"""Hey, {customer_name}!

Your appointment has been {action_word}! ✅

📅 {service.replace('Reschedule: ', '')}
📆 {preferred_date} at {preferred_time}

The team at {business_name} will see you then. Or you can call us directly at {business_phone}.

See you soon! 💅"""
            
            await meta_service.send_text_message(customer_phone, message)
            
        # Send confirmation email if we have email
        if customer_email:
            if is_reschedule:
                # Use reschedule template for rescheduled appointments
                await email_service.send_reschedule_confirmation(
                    email=customer_email,
                    booking_id=original_booking_id,
                    new_time=f"{preferred_date} {preferred_time}",
                    name=customer_name
                )
                print(f"[EMAIL] Sent reschedule confirmation to {customer_email}")
            else:
                # Use booking confirmation for new bookings
                await email_service.send_booking_confirmation(
                    name=customer_name,
                    email=customer_email,
                    date=preferred_date,
                    time=preferred_time,
                    service=service,
                    business_name=business_name
                )
                print(f"[EMAIL] Sent booking confirmation to {customer_email}")
        
        # Track approval in customer stats
        action_type = "approved"  # Used for both new bookings and reschedules
        db_service.update_customer_stats(customer_phone, action_type, {
            "service_name": service.replace('Reschedule: ', ''),
            "status": "approved"
        })
        
        return {"success": True, "message": f"Request {action_word}, booking updated, and customer notified"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/requests/{request_id}/reject")
async def reject_request(request_id: str, reason: str = ""):
    """
    Reject a booking request and notify customer via WhatsApp with reason.
    """
    from services.meta import meta_service
    
    try:
        # Update status with reason
        result = db_service.update_booking_request(request_id, {
            "status": "rejected",
            "notes": f"Rejected: {reason}" if reason else "Rejected"
        })
        
        if not result:
            raise HTTPException(status_code=404, detail="Request not found")
        
        # Get customer info and business settings
        customer_phone = result.get("customer_phone")
        customer_name = result.get("customer_name", "there")
        
        business_settings = db_service.get_all_settings()
        # Use `or` to handle empty strings properly
        business_phone = (business_settings.get("business_phone") if business_settings else None) or "0475 921 152"
        business_name = (business_settings.get("business_name") if business_settings else None) or "ibrow threading"
        
        print(f"[DEBUG] Rejection: business_phone='{business_phone}', business_name='{business_name}'")
        
        # Build rejection message with reason if provided
        if customer_phone:
            if reason:
                message = f"""Hi {customer_name},

Unfortunately, we're unable to accommodate your appointment request.

📝 Reason: {reason}

If you'd like to discuss alternatives, please call us directly at {business_phone}.

We appreciate your understanding! 💜"""
            else:
                message = f"""Hi {customer_name},

Unfortunately, we're unable to accommodate your appointment request at this time.

For more details or to discuss alternatives, please call {business_name} directly at {business_phone}.

We'll be happy to help find a time that works! 💜"""
            
            await meta_service.send_text_message(customer_phone, message)
        
        # Track rejection in customer stats
        db_service.update_customer_stats(customer_phone, "rejected", {
            "service_name": result.get("service_name", "Appointment"),
            "status": "rejected"
        })
        
        return {"success": True, "message": "Request rejected and customer notified"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/demo-stats")
async def get_demo_stats():
    """
    Get statistics for demo usage.
    """
    try:
        # Get all demo leads
        # Note: In production, we'd use aggregation queries, but for now we'll fetch recently
        # or implement a specific stats document in Appwrite if scale requires.
        # For MVP, fetching last 100 leads is fine.
        
        leads_result = db_service._make_request(
            "GET",
            f"/databases/{db_service.db_id}/collections/demo_leads/documents",
            params={"limit": 100, "orderDesc": "created_at"}
        )
        all_leads = leads_result.get("documents", []) if leads_result else []
        
        # Filter out whitelisted numbers (admin testing)
        leads = [lead for lead in all_leads if not is_whitelisted(lead.get("phone"))]
        
        # Group by phone number
        grouped_leads = {}
        for lead in leads:
            phone = lead.get("phone")
            if not phone:
                continue
                
            if phone not in grouped_leads:
                grouped_leads[phone] = {
                    "phone": phone,
                    "name": lead.get("name", "Unknown"),
                    "business_name": lead.get("business_name", "Unknown"),
                    "latest_activity": lead.get("created_at"),
                    "last_status": lead.get("status"),
                    "attempt_count": 0,
                    "$id": lead.get("$id")  # Use latest ID
                }
            
            # Update latest info if this lead is newer
            current_time = lead.get("created_at")
            stored_time = grouped_leads[phone]["latest_activity"]
            
            if current_time > stored_time:
                grouped_leads[phone].update({
                    "name": lead.get("name", "Unknown"),
                    "business_name": lead.get("business_name", "Unknown"),
                    "latest_activity": current_time,
                    "last_status": lead.get("status"),
                    "$id": lead.get("$id")
                })
            
            grouped_leads[phone]["attempt_count"] += 1

        # Convert to list and sort by latest activity desc
        demo_users = list(grouped_leads.values())
        demo_users.sort(key=lambda x: x["latest_activity"], reverse=True)
        
        total_demos = len(leads)  # Total individual demo requests
        
        return {
            "total_demos": total_demos,
            "unique_users": len(demo_users),
            "recent_leads": demo_users[:20]  # Return grouped users
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching demo stats: {e}")
        return {"total_demos": 0, "unique_users": 0, "recent_leads": []}
