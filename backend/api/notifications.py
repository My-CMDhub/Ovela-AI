"""
Staff Notifications API Router.
Provides CRUD endpoints for managing staff notifications (callback requests, etc).
Used by the dashboard for human-in-loop operations tracking.

Production-ready with:
- Status transition validation
- Soft delete (archive, not hard delete)
- Clear error messages for staff
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.appwrite import db_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ============ Status Transition Rules ============
# Only allow valid state transitions to prevent data corruption

VALID_TRANSITIONS = {
    "pending": ["in_progress", "completed", "dismissed"],
    "in_progress": ["completed", "dismissed", "pending"],  # Allow going back to pending if needed
    "completed": ["pending"],  # Allow reopening if mistake
    "dismissed": ["pending"],  # Allow reopening if mistake
}

def validate_status_transition(current_status: str, new_status: str) -> tuple[bool, str]:
    """
    Validate if a status transition is allowed.
    Returns (is_valid, error_message)
    """
    if current_status == new_status:
        return True, ""  # No change, always valid
    
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if new_status in allowed:
        return True, ""
    
    # Provide helpful error message for staff
    if current_status == "completed":
        return False, f"This request is already completed. To make changes, first reopen it by setting status back to 'pending'."
    elif current_status == "dismissed":
        return False, f"This request was dismissed. To make changes, first reopen it by setting status back to 'pending'."
    else:
        return False, f"Cannot change from '{current_status}' to '{new_status}'. Allowed transitions: {', '.join(allowed)}"


# ============ Request Models ============

class NotificationUpdate(BaseModel):
    status: Optional[str] = None  # pending, in_progress, completed, dismissed
    staff_notes: Optional[str] = None


class NotificationCreate(BaseModel):
    notification_type: str = "callback_request"
    customer_name: str
    customer_phone: str
    reason: str
    urgency: str = "medium"  # low, medium, high
    tenant_id: str = "coalcreek"


# ============ Endpoints ============

@router.post("")
async def create_notification(data: NotificationCreate):
    """
    Manually create a staff notification (e.g., from dashboard).
    """
    # Validate required fields
    if not data.customer_name or not data.customer_name.strip():
        raise HTTPException(status_code=400, detail="Customer name is required")
    if not data.customer_phone or not data.customer_phone.strip():
        raise HTTPException(status_code=400, detail="Customer phone is required")
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required")
    if data.urgency not in ["low", "medium", "high"]:
        raise HTTPException(status_code=400, detail="Urgency must be 'low', 'medium', or 'high'")
    
    try:
        result = await db_service.create_staff_notification(
            notification_type=data.notification_type,
            customer_name=data.customer_name.strip(),
            customer_phone=data.customer_phone.strip(),
            reason=data.reason.strip(),
            urgency=data.urgency,
            tenant_id=data.tenant_id
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create notification. Please try again.")
        
        logger.info(f"Created notification for {data.customer_name} ({data.notification_type})")
        return {"success": True, "notification": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again or contact support.")


@router.get("/counts")
async def get_notification_counts(tenant_id: str = "coalcreek"):
    """
    Get notification counts by status for tab badges.
    Returns: {pending: N, in_progress: N, completed: N, dismissed: N, total: N}
    """
    try:
        notifications = await db_service.get_staff_notifications(limit=500, tenant_id=tenant_id)
        
        # Filter out archived
        active = [n for n in notifications if n.get("status") != "archived"]
        
        counts = {
            "pending": len([n for n in active if n.get("status") == "pending"]),
            "in_progress": len([n for n in active if n.get("status") == "in_progress"]),
            "completed": len([n for n in active if n.get("status") == "completed"]),
            "dismissed": len([n for n in active if n.get("status") == "dismissed"]),
            "total": len(active)
        }
        return counts
    except Exception as e:
        logger.error(f"Error getting notification counts: {e}")
        raise HTTPException(status_code=500, detail="Failed to load counts.")


@router.get("")
async def list_notifications(
    status: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 50,
    include_archived: bool = False,
    tenant_id: str = "coalcreek"
):
    """
    List all staff notifications with optional filters.
    By default, excludes archived (soft-deleted) notifications.
    """
    try:
        notifications = await db_service.get_staff_notifications(
            status=status,
            notification_type=type,
            limit=limit,
            tenant_id=tenant_id
        )
        
        # Filter out archived unless explicitly requested
        if not include_archived:
            notifications = [n for n in notifications if n.get("status") != "archived"]
        
        return {"notifications": notifications, "count": len(notifications)}
    except Exception as e:
        logger.error(f"Error listing notifications: {e}")
        raise HTTPException(status_code=500, detail="Failed to load notifications. Please refresh the page.")


@router.get("/{notification_id}")
async def get_notification(notification_id: str, tenant_id: str = "coalcreek"):
    """Get a single notification by ID."""
    try:
        notifications = await db_service.get_staff_notifications(tenant_id=tenant_id)
        notification = next((n for n in notifications if n.get("$id") == notification_id), None)
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found. It may have been archived or doesn't exist.")
        
        return notification
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting notification: {e}")
        raise HTTPException(status_code=500, detail="Failed to load notification. Please try again.")


@router.patch("/{notification_id}")
async def update_notification(notification_id: str, update: NotificationUpdate, tenant_id: str = "coalcreek"):
    """
    Update a notification (change status, add notes).
    Enforces valid status transitions.
    When a booking_approval is marked 'completed', syncs reservation and sends guest email.
    """
    try:
        # Get current notification to check status transition
        notifications = await db_service.get_staff_notifications(tenant_id=tenant_id)
        current = next((n for n in notifications if n.get("$id") == notification_id), None)
        
        if not current:
            raise HTTPException(status_code=404, detail="Notification not found. It may have been archived.")
        
        data = {}
        
        # Validate status transition
        if update.status:
            current_status = current.get("status", "pending")
            is_valid, error_msg = validate_status_transition(current_status, update.status)
            
            if not is_valid:
                raise HTTPException(status_code=400, detail=error_msg)
            
            data["status"] = update.status
        
        # Allow notes update
        if update.staff_notes is not None:
            data["staff_notes"] = update.staff_notes
        
        if not data:
            raise HTTPException(status_code=400, detail="No updates provided. Please specify status or notes to update.")
        
        result = await db_service.update_staff_notification(notification_id, data)
        
        if not result:
            raise HTTPException(status_code=500, detail="Update failed. Please try again.")
        
        logger.info(f"Updated notification {notification_id}: {list(data.keys())}")
        
        # If completing a booking_approval, sync reservation & send guest email
        if update.status == "completed" and current.get("type") == "booking_approval":
            import json
            import requests
            import asyncio
            from core.config import settings
            from services.email import email_service
            
            MOTEL_DB_ID = "6947b8300005f5863f96"
            
            # Parse extra_data for booking info
            extra_data_str = current.get("extra_data", "{}")
            try:
                extra_data = json.loads(extra_data_str) if isinstance(extra_data_str, str) else extra_data_str
            except:
                extra_data = {}
            
            booking_reference = extra_data.get("booking_reference", "")
            guest_email = extra_data.get("guest_email", "")
            
            # Update reservation status to 'confirmed'
            if booking_reference:
                headers = {
                    "Content-Type": "application/json",
                    "X-Appwrite-Project": settings.APPWRITE_PROJECT_ID,
                    "X-Appwrite-Key": settings.APPWRITE_API_KEY
                }
                
                url = f"{settings.APPWRITE_ENDPOINT}/databases/{MOTEL_DB_ID}/collections/motel_reservations/documents"
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    reservations = response.json().get("documents", [])
                    matching = [r for r in reservations if r.get("booking_reference") == booking_reference]
                    if matching:
                        reservation_id = matching[0]["$id"]
                        patch_url = f"{url}/{reservation_id}"
                        patch_response = requests.patch(
                            patch_url,
                            headers=headers,
                            json={"data": {"status": "confirmed"}}
                        )
                        if patch_response.status_code in [200, 201]:
                            logger.info(f"✅ Updated reservation {booking_reference} to 'confirmed' via dashboard")
            
            # Send guest confirmation email ONLY on first completion (prevent duplicates)
            is_first_completion = not extra_data.get("link_consumed") and not extra_data.get("email_sent_via_dashboard")
            if guest_email and is_first_completion:
                # Mark that email was sent
                extra_data["email_sent_via_dashboard"] = True
                await db_service.update_staff_notification(notification_id, {
                    "extra_data": json.dumps(extra_data)
                })
                
                asyncio.create_task(
                    email_service.send_guest_booking_confirmation(
                        guest_email=guest_email,
                        guest_name=current.get("customer_name", "Guest"),
                        booking_reference=booking_reference,
                        room_type=extra_data.get("room_type", "queen"),
                        check_in=extra_data.get("check_in", ""),
                        check_out=extra_data.get("check_out", ""),
                        num_nights=extra_data.get("num_nights", 1),
                        total_amount=extra_data.get("total_amount", 0)
                    )
                )
                logger.info(f"📧 Sending guest confirmation to {guest_email} via dashboard complete")
            elif guest_email and not is_first_completion:
                logger.info(f"📧 Skipping duplicate email - guest was already notified")
        
        return {"success": True, "notification": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notification: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str, tenant_id: str = "coalcreek"):
    """
    Soft delete (archive) a notification.
    Sets status to 'archived' instead of hard deleting.
    This preserves data for auditing and allows recovery if needed.
    """
    try:
        # Get current notification
        notifications = await db_service.get_staff_notifications(tenant_id=tenant_id)
        current = next((n for n in notifications if n.get("$id") == notification_id), None)
        
        if not current:
            raise HTTPException(status_code=404, detail="Notification not found. It may already be archived.")
        
        # Don't allow archiving already-archived items
        if current.get("status") == "archived":
            raise HTTPException(status_code=400, detail="This notification is already archived.")
        
        # Soft delete: mark as archived instead of hard delete
        result = await db_service.update_staff_notification(notification_id, {
            "status": "archived",
            "staff_notes": f"{current.get('staff_notes', '')}\n[Archived by staff]".strip()
        })
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to archive. Please try again.")
        
        logger.info(f"Archived notification {notification_id}")
        return {"success": True, "message": "Notification archived. It can be recovered if needed."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving notification: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.post("/{notification_id}/restore")
async def restore_notification(notification_id: str, tenant_id: str = "coalcreek"):
    """
    Restore an archived notification back to pending status.
    """
    try:
        notifications = await db_service.get_staff_notifications(tenant_id=tenant_id)
        current = next((n for n in notifications if n.get("$id") == notification_id), None)
        
        if not current:
            raise HTTPException(status_code=404, detail="Notification not found.")
        
        if current.get("status") != "archived":
            raise HTTPException(status_code=400, detail="This notification is not archived.")
        
        result = await db_service.update_staff_notification(notification_id, {
            "status": "pending",
            "staff_notes": f"{current.get('staff_notes', '')}\n[Restored by staff]".strip()
        })
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to restore. Please try again.")
        
        logger.info(f"Restored notification {notification_id}")
        return {"success": True, "message": "Notification restored to pending status."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring notification: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
