"""
Staff Notifications API Router.
Provides CRUD endpoints for managing staff notifications (callback requests, etc).
Used by the dashboard for human-in-loop operations tracking.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.appwrite import db_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


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


# ============ Endpoints ============

@router.post("")
async def create_notification(data: NotificationCreate):
    """
    Manually create a staff notification (e.g., from dashboard).
    """
    try:
        result = db_service.create_staff_notification(
            notification_type=data.notification_type,
            customer_name=data.customer_name,
            customer_phone=data.customer_phone,
            reason=data.reason,
            urgency=data.urgency
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create notification")
        
        return {"success": True, "notification": result}
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("")
async def list_notifications(
    status: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 50
):
    """
    List all staff notifications with optional filters.
    """
    try:
        notifications = db_service.get_staff_notifications(
            status=status,
            notification_type=type,
            limit=limit
        )
        return {"notifications": notifications, "count": len(notifications)}
    except Exception as e:
        logger.error(f"Error listing notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{notification_id}")
async def get_notification(notification_id: str):
    """Get a single notification by ID."""
    try:
        notifications = db_service.get_staff_notifications()
        notification = next((n for n in notifications if n.get("$id") == notification_id), None)
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return notification
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{notification_id}")
async def update_notification(notification_id: str, update: NotificationUpdate):
    """
    Update a notification (change status, add notes).
    """
    try:
        data = {}
        if update.status:
            data["status"] = update.status
        if update.staff_notes is not None:
            data["staff_notes"] = update.staff_notes
        
        if not data:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        result = db_service.update_staff_notification(notification_id, data)
        
        if not result:
            raise HTTPException(status_code=404, detail="Notification not found or update failed")
        
        return {"success": True, "notification": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str):
    """Delete a notification."""
    try:
        success = db_service.delete_staff_notification(notification_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Notification not found or delete failed")
        
        return {"success": True, "message": "Notification deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))
