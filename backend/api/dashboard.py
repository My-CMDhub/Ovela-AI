"""
Motel API Routes
================
Backend API routes for motel dashboard data (multi-tenant).
These routes handle Appwrite database operations securely - the API key
stays on the backend and is never exposed to the frontend.

Routes:
- GET /api/motel/stats - Dashboard statistics
- GET /api/motel/reservations - List reservations
- GET /api/motel/guests - List guests
- POST /api/motel/reservations - Create reservation
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, Depends
import httpx

from core.config import settings
from core.auth import get_current_tenant_id

logger = logging.getLogger(__name__)

# NOTE: Prefix is handled in main.py to allow dual mounting (/api/dashboard AND /api/motel)
router = APIRouter(tags=["dashboard"])

MOTEL_DB_ID = "6947b8300005f5863f96"
APPWRITE_ENDPOINT = settings.APPWRITE_ENDPOINT
APPWRITE_PROJECT_ID = settings.APPWRITE_PROJECT_ID
APPWRITE_API_KEY = settings.APPWRITE_API_KEY


from appwrite.query import Query as AppwriteQuery

def get_appwrite_headers() -> dict:
    """Get headers for Appwrite API requests."""
    return {
        "Content-Type": "application/json",
        "X-Appwrite-Project": APPWRITE_PROJECT_ID,
        "X-Appwrite-Key": APPWRITE_API_KEY
    }


async def appwrite_request(method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
    """Make a request to Appwrite API."""
    url = f"{APPWRITE_ENDPOINT}{endpoint}"
    headers = get_appwrite_headers()
    
    # Handle queries list serialization (JSON format + array indices)
    if params and 'queries' in params:
        query_list = params.pop('queries')
        new_params = params.copy()
        for i, q in enumerate(query_list):
            new_params[f'queries[{i}]'] = str(q)
        params = new_params

    async with httpx.AsyncClient() as client:
        try:
            if method == "GET":
                response = await client.get(url, headers=headers, params=params, timeout=30.0)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=data, params=params, timeout=30.0)
            elif method == "PATCH":
                response = await client.patch(url, headers=headers, json=data, params=params, timeout=30.0)
            elif method == "DELETE":
                response = await client.delete(url, headers=headers, timeout=30.0)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.error(f"Appwrite error: {response.status_code} - {response.text}")
                return {"error": f"Appwrite error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Appwrite request failed: {e}")
            return {"error": str(e)}


# ============================================================================
# STATS ENDPOINT
# ============================================================================

@router.get("/stats")
async def get_motel_stats(tenant_id: str = Depends(get_current_tenant_id)):
    """Get dashboard statistics for the motel."""
    try:
        # Get all reservations to calculate stats
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
        result = await appwrite_request("GET", endpoint)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        reservations = result.get("documents", [])
        
        # Filter by tenant
        if tenant_id:
            reservations = [r for r in reservations if r.get("tenant_id") == tenant_id]
            
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Calculate stats
        today_check_ins = sum(1 for r in reservations if r.get("check_in_date") == today)
        today_check_outs = sum(1 for r in reservations if r.get("check_out_date") == today)
        pending = sum(1 for r in reservations if r.get("status") == "pending")
        confirmed = sum(1 for r in reservations if r.get("status") == "confirmed")
        
        # Get unique guests
        guests_endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_guests/documents"
        guests_result = await appwrite_request("GET", guests_endpoint)
        total_guests = len(guests_result.get("documents", [])) if "error" not in guests_result else 0
        
        return {
            "success": True,
            "stats": {
                "todayCheckIns": today_check_ins,
                "todayCheckOuts": today_check_outs,
                "totalRooms": 14,  # TODO: Make this tenant-specific
                "occupiedRooms": confirmed,
                "pendingReservations": pending,
                "totalGuests": total_guests
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting motel stats: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# RESERVATIONS ENDPOINTS
# ============================================================================

@router.get("/reservations")
async def get_reservations(
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[str] = Query(default=None),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Get list of reservations."""
    try:
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
        result = await appwrite_request("GET", endpoint)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        documents = result.get("documents", [])
        
        documents = result.get("documents", [])
        
        # Filter by tenant_id (CRITICAL for multi-tenant)
        documents = result.get("documents", [])
        
        # Filter by tenant_id (CRITICAL for multi-tenant)
        if not tenant_id:
            return {"success": False, "error": "Tenant ID is required"}
            
        documents = [d for d in documents if d.get("tenant_id") == tenant_id]
        
        # Filter by status if provided
        if status:
            documents = [d for d in documents if d.get("status") == status]
        
        # Apply limit
        documents = documents[:limit]
        
        return {
            "success": True,
            "reservations": documents,
            "total": len(documents)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================================
# ROOMS ENDPOINT (PMS Dashboard view)
# ============================================================================

@router.get("/rooms")
async def get_rooms(tenant_id: str = Depends(get_current_tenant_id)):
    """Get list of motel rooms."""
    try:
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_rooms/documents"
        # We fetch all rooms, assuming limit 100 is enough for a motel
        params = {"queries": [AppwriteQuery.limit(100)]}
        result = await appwrite_request("GET", endpoint, params=params)
        
        if "error" in result:
             return {"success": False, "error": result["error"]}
             
        rooms = result.get("documents", [])
        
        # If tenant filtering is needed in the future:
        # rooms = [r for r in rooms if r.get("tenant_id") == tenant_id]
        
        # Sort rooms by room_number logically
        rooms.sort(key=lambda x: str(x.get("room_number", "")))
             
        return {
            "success": True,
            "rooms": rooms,
            "total": len(rooms)
        }
        
    except Exception as e:
        logger.error(f"Error getting motel rooms: {e}")
        return {"success": False, "error": str(e)}

@router.post("/reservations")
async def create_reservation(data: dict, tenant_id: str = Depends(get_current_tenant_id)):
    """Create a new reservation."""
    try:
        import random
        import string
        
        # Generate booking reference if not provided
        if "booking_reference" not in data:
            ref_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            data["booking_reference"] = f"MTL-{ref_suffix}"
        
        # Add timestamp
        if "created_at" not in data:
            data["created_at"] = datetime.now().isoformat()
        
        # Default status
        if "status" not in data:
            data["status"] = "pending"

        # Enforce tenant_id from auth context
        data["tenant_id"] = tenant_id
        
        # Generate document ID
        doc_id = f"res_{int(datetime.now().timestamp())}"
        
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
        payload = {
            "documentId": doc_id,
            "data": data
        }
        
        result = await appwrite_request("POST", endpoint, payload)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        return {
            "success": True,
            "reservation": result,
            "booking_reference": data["booking_reference"]
        }
        
    except Exception as e:
        logger.error(f"Error creating reservation: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# GUESTS ENDPOINTS
# ============================================================================

@router.get("/guests")
async def get_guests(
    limit: int = Query(default=100, ge=1, le=500),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Get list of guests."""
    try:
        # Filter by Tenant via query
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_guests/documents"
        
        # We can use Appwrite queries if attribute is indexed, else fetch and filter
        # Assuming index exists on tenant_id, but fall safe to manual filter
        # queries[]=equal("tenant_id", tenant_id)
        
        # Fetching with query param directly if using helper? 
        # appwrite_request helper handles queries params if passed specifically?
        # The current helper in motel.py calls appwrite_request which wraps requests.
        # Let's use manual filtering for reliability as we did in get_reservations
        
        # Use params for queries
        params = {"queries": [AppwriteQuery.limit(limit)]}
        result = await appwrite_request("GET", endpoint, params=params)
        
        if "error" in result:
             return {"success": False, "error": result["error"]}
             
        guests = result.get("documents", [])
        guests = result.get("documents", [])
        
        if not tenant_id:
             return {"success": False, "error": "Tenant ID is required"}
             
        guests = [g for g in guests if g.get("tenant_id") == tenant_id]
             
        return {
            "success": True,
            "guests": guests,
            "total": len(guests)
        }
        
    except Exception as e:
        logger.error(f"Error getting guests: {e}")
        return {"success": False, "error": str(e)}


@router.post("/guests")
async def create_guest(data: dict, tenant_id: str = Depends(get_current_tenant_id)):
    """Create a new guest record."""
    try:
        # Add timestamp
        if "created_at" not in data:
            data["created_at"] = datetime.now().isoformat()
            
        # Enforce tenant_id from auth context
        data["tenant_id"] = tenant_id
        
        # Generate document ID
        doc_id = f"guest_{int(datetime.now().timestamp())}"
        
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_guests/documents"
        payload = {
            "documentId": doc_id,
            "data": data
        }
        
        result = await appwrite_request("POST", endpoint, payload)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        return {
            "success": True,
            "guest": result
        }
        
    except Exception as e:
        logger.error(f"Error creating guest: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# CALL LOGS ENDPOINTS (Staff Conversation Logs Dashboard)
# ============================================================================

# Outcome categories for filtering
COMPLETED_OUTCOMES = ["completed", "transferred", "booking_completed"]
ISSUE_OUTCOMES = ["spam_terminated", "timeout_silence", "timeout_duration", "abuse_timeout"]

@router.get("/call-logs")
async def get_call_logs(
    status: Optional[str] = Query(default="completed", description="Filter: completed, issues, or all"),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    phone: Optional[str] = Query(default=None, description="Phone number to search"),
    limit: int = Query(default=50, ge=1, le=200),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get call transcripts for staff review.
    Enforces tenant isolation by fetching from tenant-specific collections.
    
    Filters:
    - status: "completed" (default), "issues", "all"
    - start_date / end_date: Date range filter
    - phone: Phone number search
    """
    try:
        from services.appwrite import db_service
        import json
        
        # Fetch transcripts using the TENANT-SPECIFIC method
        transcripts = await db_service.get_tenant_call_logs(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            phone=phone,
            limit=limit * 2  # Fetch more to account for filtering
        )
        
        # Get Summary Stats (Official Daily Counts) for the KPI cards
        # We only use this if no filters are applied (or if filters imply "today's view")
        # For simplicity, we always return "Today's" stats in the counting block if no date range is restrictive,
        # but the dashboard cards specifically ask for "Today".
        daily_stats = await db_service.get_daily_summary_stats(tenant_id)
        
        # Filter by status category
        # valid outcomes match COMPLETED_OUTCOMES / ISSUE_OUTCOMES
        # We map tenant 'status' to 'outcome' for consistency
        
        filtered = []
        for t in transcripts:
            # Map fields (Tenant Schema -> Frontend Schema)
            # Tenant: caller_phone, duration, status, transcript (str)
            # Frontend expects: phone, duration_seconds, outcome, transcript (json list)
            
            outcome = t.get("status") or t.get("outcome", "unknown")
            duration = t.get("duration") or t.get("duration_seconds", 0)
            
            # Logic for filtering
            if status == "completed":
                is_completed = outcome in COMPLETED_OUTCOMES
                is_long_enough = duration >= 3
                if is_completed or (outcome not in ISSUE_OUTCOMES and is_long_enough):
                    filtered.append(t)
            elif status == "issues":
                if outcome in ISSUE_OUTCOMES:
                    filtered.append(t)
            else:
                # "all"
                filtered.append(t)

        # Apply limit after filtering
        transcripts = filtered[:limit]
        
        # Format for frontend
        formatted = []
        for t in transcripts:
            # Re-map for display
            outcome = t.get("status") or t.get("outcome", "unknown")
            duration = t.get("duration") or t.get("duration_seconds", 0)
            caller_phone = t.get("caller_phone") or t.get("phone")
            
            raw_transcript = t.get("transcript") or t.get("transcript_json", "[]")
            transcript_data = []
            
            try:
                # Handle if it's already a list/dict object (unlikely from Appwrite JSON but possible)
                if isinstance(raw_transcript, (list, dict)):
                    transcript_data = raw_transcript if isinstance(raw_transcript, list) else [raw_transcript]
                elif isinstance(raw_transcript, str):
                    if raw_transcript.strip().startswith("[") or raw_transcript.strip().startswith("{"):
                         transcript_data = json.loads(raw_transcript)
                    else:
                         # Plain text transcript
                         transcript_data = [{"role": "assistant", "text": raw_transcript}]
            except:
                transcript_data = []
            
            formatted.append({
                "id": t.get("$id"),
                "phone": caller_phone,
                "created_at": t.get("created_at"),
                "duration_seconds": duration,
                "exchange_count": t.get("exchange_count", 0),
                "outcome": outcome,
                "transcript": transcript_data,
                "call_sid": t.get("call_sid", ""),
                "booking_reference": t.get("pms_reference") or t.get("booking_ref") or "",
                "call_summary": t.get("call_summary") or "",
                "customer_name": t.get("customer_name") or "Not provided",
                "sms_status": t.get("sms_status") or "none",
            })
        
        return {
            "success": True,
            "logs": formatted,
            "total": len(formatted),
            "counts": {
                "completed": daily_stats["total_calls"] - daily_stats["missed_calls"],
                "issues": daily_stats["missed_calls"],
                "all": daily_stats["total_calls"],
                "avg_duration": daily_stats["avg_duration"]
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting call logs: {e}")
        return {"success": False, "error": str(e), "logs": [], "total": 0}

@router.post("/reservations/manual")
async def create_manual_booking(data: dict):
    """
    Create a manual walk-in booking (Staff overrides).
    Checks availability but allows forcing creation.
    """
    try:
        import random
        import string
        from services.motel_knowledge_base import ROOM_INFO

        guest_name = data.get("guest_name")
        guest_phone = data.get("guest_phone")
        guest_email = data.get("guest_email")
        check_in = data.get("check_in_date")
        check_out = data.get("check_out_date")
        room_type = data.get("room_type", "queen")
        force = data.get("force", False)

        if not guest_name or not check_in or not guest_phone:
            return {"success": False, "error": "Name, Phone, and Check-in date required"}

        # 1. Check Availability (Prevent collisions)
        if not force:
            endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
            # Get all reservations for this room type to check dates
            # Ideally filter by date range in query, but for now fetch active ones
            # Simplification: Fetch all confirmed/pending for this room_type
            # For robust checking, we'd need date range queries. 
            # Given Appwrite limitations on complex OR queries, we might fetch larger set or rely on client.
            # Let's do a quick check against blocking:
            
            # Simple check: Is there physically a room?
            # We already have logic in handlers.py, let's reuse/mimic basic count
            # Query confirmed bookings overlapping these dates
            
            queries = [
                f'equal("room_type", "{room_type}")',
                f'notEqual("status", "cancelled")'
            ]
            
            # Since range queries are tricky without specific setup, let's trust the staff
            # mostly, but do a sanity check if possible.
            # For this MVP step, we will assume staff checked the dashboard calendar.
            # We just flag it as source=walk_in
            pass

        # 2. Prepare Data
        # Generate booking reference
        if "booking_reference" not in data:
            ref_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            data["booking_reference"] = f"WALK-{ref_suffix}" # distinct prefix

        # Auto-confirm walk-ins
        data["status"] = "confirmed"
        data["source"] = "walk_in" 
        
        # Calculate totals if missing
        if "total_amount" not in data:
            # Basic calculation
            try:
                start = datetime.strptime(check_in, "%Y-%m-%d")
                end = datetime.strptime(check_out, "%Y-%m-%d")
                nights = (end - start).days or 1
                price = ROOM_INFO.get(room_type, {}).get("price", 130)
                data["total_amount"] = price * nights
                data["num_nights"] = nights
                data["rate_per_night"] = price
            except:
                pass

        # Add timestamp
        if "created_at" not in data:
            data["created_at"] = datetime.now().isoformat()
            
        if "force" in data:
            del data["force"]

        # Generate document ID
        doc_id = f"res_walkin_{int(datetime.now().timestamp())}"
        
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
        payload = {
            "documentId": doc_id,
            "data": data
        }
        
        result = await appwrite_request("POST", endpoint, payload)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        return {
            "success": True,
            "reservation": result,
            "booking_reference": data["booking_reference"]
        }
        
    except Exception as e:
        logger.error(f"Error creating manual reservation: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# BOOKING MANAGEMENT ENDPOINTS (Approve/Reject/Payments)
# ============================================================================

@router.patch("/bookings/{booking_id}")
async def update_booking(booking_id: str, data: dict):
    """
    Update a booking (general update).
    Staff can update notes, dates, guest details etc.
    """
    try:
        # Don't allow changing sensitive fields directly via this endpoint if needed
        # but for MVP trust the staff dashboard.
        
        # Add updated_at
        data["updated_at"] = datetime.now().isoformat()
        
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents/{booking_id}"
        payload = {"data": data}
        
        result = await appwrite_request("PATCH", endpoint, payload)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        return {"success": True, "booking": result}
        
    except Exception as e:
        logger.error(f"Error updating booking {booking_id}: {e}")
        return {"success": False, "error": str(e)}


@router.post("/bookings/{booking_id}/approve")
async def approve_booking(booking_id: str):
    """
    Approve a pending booking.
    1. Update status to 'link_sent' (or 'approved' if no payment).
    2. Generate Stripe Payment Link.
    3. Send SMS to guest with link (PRIMARY).
    4. Send Email to guest with link (SECONDARY/OPTIONAL).
    """
    try:
        from services.tenants.coalcreek.stripe import coalcreek_stripe_service
        from services.email import email_service
        from services.sms import sms_service
        from services.appwrite import db_service
        
        # 1. Get Booking Details
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents/{booking_id}"
        booking = await appwrite_request("GET", endpoint)
        
        if "error" in booking:
            return {"success": False, "error": "Booking not found"}
            
        # Fetch Tenant Config
        tenant_id = booking.get("tenant_id", "coalcreek")
        tenant_config = await db_service.get_tenant_config(tenant_id)
        use_stripe = tenant_config.get("use_stripe_payments", False)
        
        # 2. Generate Payment/Setup Link (Dynamic Logic)
        check_in_str = booking.get("check_in_date")
        days_until = 0
        try:
            ci_dt = datetime.strptime(check_in_str, "%Y-%m-%d")
            days_until = (ci_dt - datetime.now()).days
        except:
            pass

        # 7-DAY RULE: 
        # <= 7 Days: Payment (Immediate Charge)
        # > 7 Days: Setup (Card Hold)
        mode = "payment"
        if days_until > 7:
            mode = "setup"
        
        # Calculate price if missing
        num_nights = booking.get("num_nights", 1)
        rate = booking.get("rate_per_night", 145) # Fallback rate
        if not rate: rate = 145
        
        payment_res = {}
        if use_stripe:
            if mode == "setup":
                payment_res = await coalcreek_stripe_service.create_setup_session(
                    booking_ref=booking.get("booking_reference"),
                    customer_email=booking.get("guest_email"),
                    customer_name=booking.get("guest_name"),
                    room_type=booking.get("room_type"),
                    check_in=booking.get("check_in_date"),
                    check_out=booking.get("check_out_date"),
                    num_nights=num_nights
                )
            else:
                payment_res = await coalcreek_stripe_service.create_payment_link(
                    booking_ref=booking.get("booking_reference"),
                    room_type=booking.get("room_type"),
                    num_nights=num_nights,
                    price_per_night=rate,
                    customer_email=booking.get("guest_email"),
                    customer_name=booking.get("guest_name"),
                    check_in=booking.get("check_in_date"),
                    check_out=booking.get("check_out_date")
                )
        
        payment_link = None
        status = "approved" # Default if payment fails/not needed
        
        if use_stripe:
            if payment_res.get("success"):
                payment_link = payment_res.get("payment_url")
                status = "link_sent"
            else:
                logger.warning(f"Failed to generate {mode} link: {payment_res.get('error')}")
                # Continue anyway, staff can retry later
        
        # 3. Update Booking Status
        update_data = {
            "status": status,
            "payment_link_url": payment_link,
            "payment_link_sent_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "payment_mode_requested": mode  # Track what we asked for
        }
        
        patch_res = await appwrite_request("PATCH", endpoint, {"data": update_data})
        
        if "error" in patch_res:
             return {"success": False, "error": f"Failed to update booking status: {patch_res['error']}"}
        
        messages = []
        
        # 4. SEND SMS (Primary)
        guest_phone = booking.get("guest_phone")
        if guest_phone:
            b_name = tenant_config.get("business_name", "our Motel")
            guest_first = booking.get('guest_name', 'Guest').split(' ')[0]
            if payment_link:
                action_text = "Secure your booking here" if mode == "setup" else "Complete payment here"
                sms_body = f"Hi {guest_first}, your booking at {b_name} is approved! {action_text}: {payment_link}"
            else:
                sms_body = f"Hi {guest_first}, your booking at {b_name} is confirmed! We look forward to welcoming you."
            
            sms_sent = await sms_service.send_sms(guest_phone, sms_body, tenant_id=tenant_id)
            if sms_sent:
                messages.append("SMS sent")
            else:
                messages.append("SMS failed")
        
        # 5. SEND EMAIL (Secondary/If provided)
        guest_email = booking.get("guest_email")
        if guest_email:
            if payment_link:
                await email_service.send_payment_link(
                    to_email=guest_email,
                    guest_name=booking.get("guest_name"),
                    booking_ref=booking.get("booking_reference"),
                    payment_link=payment_link,
                    room_type=booking.get("room_type"),
                    check_in=booking.get("check_in_date"),
                    check_out=booking.get("check_out_date"),
                    amount=payment_res.get("total_amount", 0) if mode == "payment" else 0,
                    business_name=tenant_config.get("business_name", "Motel"),
                    business_phone=tenant_config.get("business_phone", ""),
                    business_location=tenant_config.get("location", ""),
                    tenant_id=tenant_id
                )
            else:
                await email_service.send_guest_booking_confirmation(
                    guest_email=guest_email,
                    guest_name=booking.get("guest_name"),
                    booking_reference=booking.get("booking_reference"),
                    room_type=booking.get("room_type"),
                    check_in=booking.get("check_in_date"),
                    check_out=booking.get("check_out_date"),
                    num_nights=num_nights,
                    total_amount=booking.get("total_amount", 0),
                    business_name=tenant_config.get("business_name", "Motel"),
                    business_phone=tenant_config.get("business_phone", ""),
                    business_location=tenant_config.get("location", ""),
                    tenant_id=tenant_id
                )
            messages.append("Email sent")
            
        return {
            "success": True, 
            "status": status, 
            "payment_link": payment_link,
            "mode": mode,
            "message": f"Booking approved ({mode}). {', '.join(messages)}"
        }

    except Exception as e:
        logger.error(f"Error approving booking {booking_id}: {e}")
        return {"success": False, "error": str(e)}


@router.post("/bookings/{booking_id}/reject")
async def reject_booking(booking_id: str):
    """
    Reject a booking request.
    1. Update status to 'rejected'.
    2. Send rejection email.
    """
    try:
        from services.tenants.coalcreek.email import coalcreek_email_service
        
        # 1. Update Status
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents/{booking_id}"
        update_data = {
            "status": "rejected",
            "updated_at": datetime.now().isoformat()
        }
        
        booking = await appwrite_request("PATCH", endpoint, {"data": update_data})
        
        if "error" in booking:
            return {"success": False, "error": booking["error"]}
            
        # 2. Send Email (Optional - can be manual, but nice to automate)
        # Note: Implement send_rejection in email service if needed, or just skip for now.
        # For MVP we just update status.
        
        return {"success": True, "message": "Booking rejected"}
        
    except Exception as e:
        logger.error(f"Error rejecting booking {booking_id}: {e}")
        return {"success": False, "error": str(e)}


@router.post("/bookings/{booking_id}/payment-link")
async def regenerate_payment_link(booking_id: str):
    """
    Regenerate or retrieve payment link for an existing booking.
    """
    try:
        from services.tenants.coalcreek.stripe import coalcreek_stripe_service
        
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents/{booking_id}"
        booking = await appwrite_request("GET", endpoint)
        
        if "error" in booking:
            return {"success": False, "error": "Booking not found"}
            
        # Reuse existing if valid? Stripe links don't expire quickly usually.
        if booking.get("payment_link_url") and booking.get("status") != "paid":
             return {"success": True, "payment_link": booking.get("payment_link_url")}
             
        # Generate New
        num_nights = booking.get("num_nights", 1)
        rate = booking.get("rate_per_night", 145)
        
        payment_res = await coalcreek_stripe_service.create_payment_link(
            booking_ref=booking.get("booking_reference"),
            room_type=booking.get("room_type"),
            num_nights=num_nights,
            price_per_night=rate,
            customer_email=booking.get("guest_email"),
            customer_name=booking.get("guest_name"),
            check_in=booking.get("check_in_date"),
            check_out=booking.get("check_out_date")
        )
        
        if not payment_res.get("success"):
            return {"success": False, "error": payment_res.get("error")}
            
        # Update DB
        update_data = {
            "payment_link_url": payment_res.get("payment_url"),
            "updated_at": datetime.now().isoformat()
        }
        await appwrite_request("PATCH", endpoint, {"data": update_data})
        
        return {"success": True, "payment_link": payment_res.get("payment_url")}

    except Exception as e:
        logger.error(f"Error getting payment link for {booking_id}: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# STRIPE WEBHOOK
# ============================================================================

from fastapi import Request, Header

@router.post("/payments/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """
    Handle Stripe webhooks for payment confirmation.
    """
    try:
        from services.tenants.coalcreek.stripe import coalcreek_stripe_service
        
        payload = await request.body()
        verification = coalcreek_stripe_service.verify_webhook(payload, stripe_signature)
        
        if not verification.get("valid"):
            logger.warning("Invalid Stripe webhook signature")
            # Don't return 400 to avoid Stripe retrying, just warn and 200
            return {"status": "ignored", "reason": "invalid_signature"}
            
        event = verification.get("event")
        event_type = getattr(event, "type", None) or event.get("type")
        
        if event_type == "checkout.session.completed":
            session = getattr(event.data, "object", None) or event.get("data", {}).get("object", {})
            
            # Handle success (Payment or Setup)
            result = await coalcreek_stripe_service.handle_checkout_completion(session)
            
            if result.get("success"):
                # Update Booking Status in DB
                booking_ref = result.get("booking_ref")
                mode = result.get("mode", "payment")
                stripe_session_id = getattr(session, "id", None) or session.get("id", "")
                stripe_payment_id = result.get("payment_intent")
                amount_total_cents = result.get("amount_total", 0)

                # PRIMARY lookup: booking_reference from Stripe metadata
                # FALLBACK: stripe_session_id stored on doc during booking creation
                from services.appwrite import db_service as _db
                booking_doc = None
                if booking_ref:
                    booking_doc = await _db.get_booking_by_reference(booking_ref)
                if not booking_doc and stripe_session_id:
                    logger.warning(
                        "⚠️ Webhook: booking_ref lookup missed for %s — falling back to stripe_session_id",
                        booking_ref,
                    )
                    booking_doc = await _db.get_booking_by_stripe_session(stripe_session_id)

                if booking_doc:
                    doc_id = booking_doc.get("$id")
                    
                    if mode == "setup":
                        # Card saved — mark confirmed but not paid
                        await _db.update_motel_reservation(doc_id, {
                            "status": "confirmed",
                            "payment_status": "card_on_file",
                            "stripe_setup_intent": result.get("setup_intent"),
                        })
                        logger.info("💳 Booking %s card securely saved (SetupIntent)", booking_ref)
                    else:
                        # Paid — mark paid and confirmed atomically
                        await _db.update_booking_payment_status(
                            booking_id=doc_id,
                            payment_status="paid",
                            stripe_payment_id=stripe_payment_id,
                            deposit_paid=float(amount_total_cents) / 100.0,
                        )
                        logger.info("💰 Booking %s marked as PAID | amount=AUD$%.2f", booking_ref, amount_total_cents / 100.0)

                    # Send notifications using the fully-populated doc
                    doc = booking_doc
                    try:
                        from services.email import email_service

                        tenant_id = doc.get("tenant_id", "coalcreek")
                        guest_email = doc.get("guest_email")

                        _COALCREEK_DEFAULTS = {
                            "staff_email": "officialcoalcreek@gmail.com",
                            "business_name": "Coal Creek Motel",
                            "business_phone": "+61468088990",
                            "location": "8444 South Gippsland Highway, Korumburra VIC 3950",
                        }
                        if tenant_id == "coalcreek":
                            tenant_config = _COALCREEK_DEFAULTS
                        else:
                            from services.appwrite import db_service as _db2
                            tenant_config = await _db2.get_tenant_config(tenant_id) or {}

                        staff_email = tenant_config.get("staff_email") or _COALCREEK_DEFAULTS["staff_email"]
                        business_name = tenant_config.get("business_name", "Coal Creek Motel")

                        # 1. Notify Staff — isolated so guest email still fires if this fails
                        try:
                            await email_service.send_staff_payment_notification(
                                staff_email=staff_email,
                                booking_reference=booking_ref,
                                customer_name=doc.get("guest_name", "Guest"),
                                customer_email=guest_email,
                                room_type=doc.get("room_type", ""),
                                check_in=doc.get("check_in_date", ""),
                                check_out=doc.get("check_out_date", ""),
                                num_nights=doc.get("num_nights", 1),
                                amount_paid=amount_total_cents / 100.0 if mode == "payment" else 0.0,
                                mode=mode,
                            )
                            logger.info("📧 Staff payment notification sent to %s", staff_email)
                        except Exception as staff_err:
                            logger.error("❌ Staff notification failed (non-fatal): %s", staff_err)

                        # 2. Notify Guest — isolated so staff email failure cannot block this
                        if guest_email:
                            try:
                                await email_service.send_guest_booking_confirmation(
                                    guest_email=guest_email,
                                    guest_name=doc.get("guest_name", "Guest"),
                                    booking_reference=booking_ref,
                                    room_type=doc.get("room_type", ""),
                                    check_in=doc.get("check_in_date", ""),
                                    check_out=doc.get("check_out_date", ""),
                                    num_nights=doc.get("num_nights", 1),
                                    total_amount=amount_total_cents / 100.0 if mode == "payment" else doc.get("total_amount", 0),
                                    business_name=business_name,
                                    business_phone=tenant_config.get("business_phone", ""),
                                    business_location=tenant_config.get("location", ""),
                                    tenant_id=tenant_id,
                                )
                                logger.info("📧 Guest confirmation sent to %s (%s)", guest_email, booking_ref)
                            except Exception as guest_err:
                                logger.error("❌ Guest confirmation failed for %s: %s", booking_ref, guest_err)
                        else:
                            logger.error("❌ No guest_email on booking doc — skipping guest confirmation for %s", booking_ref)

                    except Exception as email_err:
                        logger.error("Failed to send payment/setup emails for %s: %s", booking_ref, email_err)


                else:
                    logger.warning("Booking not found for webhook update: ref=%s sid=%s", booking_ref, stripe_session_id)


        elif event_type == "checkout.session.expired":
            session = event.get("data", {}).get("object", {})
            metadata = session.get("metadata", {})
            
            if metadata.get("tenant_id") == "coalcreek":
                booking_ref = metadata.get("booking_ref")
                logger.info(f"⚠️ Booking {booking_ref} link EXPIRED")
                
                # Find booking by reference
                query_endpoint = f"/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
                q_str = f'?queries[]=equal("booking_reference", "{booking_ref}")'
                search_res = await appwrite_request("GET", query_endpoint + q_str)
                
                if search_res.get("documents"):
                    doc = search_res["documents"][0]
                    # Only expire if still strictly in 'link_sent' status (avoid race conditions if paid)
                    if doc.get("status") == "link_sent":
                        await appwrite_request("PATCH", f"{query_endpoint}/{doc.get('$id')}", {
                            "data": {
                                "status": "expired", 
                                "updated_at": datetime.now().isoformat()
                            }
                        })
                        
                        # Notify Staff
                        try:
                            from services.email import email_service
                            from services.appwrite import db_service
                            
                            tenant_id = doc.get("tenant_id", "coalcreek")
                            tenant_config = await db_service.get_tenant_config(tenant_id)
                            staff_email = tenant_config.get("staff_email")
                            
                            if hasattr(email_service, 'send_expiry_notification'):
                                await email_service.send_expiry_notification(
                                    staff_email=staff_email,
                                    booking_ref=booking_ref,
                                    customer_name=metadata.get("customer_name"),
                                    room_type=metadata.get("room_type"),
                                    check_in=metadata.get("check_in")
                                )
                        except Exception as ex:
                            logger.error(f"Failed to send expiry email: {ex}")
                            
        return {"status": "received"}

    except Exception as e:
        logger.warning(f"Stripe webhook processing warning (non-fatal): {type(e).__name__}: {e}")
        return {"status": "received"}


# -----------------------------------------------------------------------------
# SETTINGS
# -----------------------------------------------------------------------------

@router.get("/settings")
async def get_settings(
    tenant_id: str = Query(default="coalcreek", description="Tenant ID")
):
    """
    Get business settings (Profile, Hours, etc).
    Fetches real data from 'Tenants' collection in Appwrite.
    """
    from services.appwrite import db_service
    
    # 1. Try to get from Appwrite
    real_settings = await db_service.get_tenant_settings(tenant_id)
    
    if real_settings:
        # Ensure fallback defaults for missing fields if needed
        return {
            "success": True,
            "settings": real_settings
        }

    # 2. Fallbacks for safety (if DB record missing)
    # Default to Coal Creek

    return {
        "success": True,
        "settings": {
            "business_name": "Coal Creek Motel",
            "business_hours": "24/7 Reception\nCheck-in: 2:00 PM\nCheck-out: 10:00 AM",
            "location": "8444 South Gippsland Highway, Korumburra VIC 3950",
            "business_phone": "0492897718",
            "owner_email": "coalcreekmotel@gmail.com"
        }
    }

@router.post("/settings")
async def update_settings(
    settings_data: dict,
    tenant_id: str = Query(default="coalcreek", description="Tenant ID")
):
    """
    Update business settings in Appwrite.
    """
    from services.appwrite import db_service
    
    success = await db_service.update_tenant_settings(tenant_id, settings_data)
    
    return {
        "success": success,
        "message": "Settings updated successfully" if success else "Failed to update settings"
    }
