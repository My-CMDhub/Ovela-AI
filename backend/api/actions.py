"""
Magic Link Actions API
Handles email-based action links for staff operations (complete, dismiss, approve, reject).
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from services.magic_links import verify_action_token
from services.appwrite import db_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actions", tags=["actions"])

# Dashboard URL for redirects
DASHBOARD_URL = "https://ovela.dev/motel/notifications"


def success_page(title: str, message: str, phone: str = None) -> str:
    """Generate a simple success HTML page."""
    phone_button = ""
    if phone:
        phone_button = f'''
        <a href="tel:{phone}" style="display: inline-block; margin-top: 20px; padding: 14px 28px; background: #8B2332; color: white; border-radius: 8px; text-decoration: none; font-weight: 600;">
            📞 Call {phone}
        </a>
        '''
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f7; margin: 0; padding: 40px 20px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; padding: 40px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            h1 {{ font-size: 24px; color: #1d1d1f; margin-bottom: 16px; }}
            p {{ color: #86868b; font-size: 16px; line-height: 1.6; }}
            .reminder {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 16px; margin-top: 24px; color: #856404; font-size: 14px; }}
            .back-link {{ margin-top: 24px; }}
            .back-link a {{ color: #0066cc; text-decoration: none; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{title}</h1>
            <p>{message}</p>
            {phone_button}
            <div class="reminder">
                ⚠️ <strong>Don't forget:</strong> Update your CRM/external system too!
            </div>
            <div class="back-link">
                <a href="{DASHBOARD_URL}">← Open Dashboard</a>
            </div>
        </div>
    </body>
    </html>
    """


def error_page(title: str, message: str) -> str:
    """Generate error HTML page."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f7; margin: 0; padding: 40px 20px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; padding: 40px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            h1 {{ font-size: 24px; color: #dc3545; margin-bottom: 16px; }}
            p {{ color: #86868b; font-size: 16px; line-height: 1.6; }}
            .back-link {{ margin-top: 24px; }}
            .back-link a {{ color: #0066cc; text-decoration: none; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>❌ {title}</h1>
            <p>{message}</p>
            <div class="back-link">
                <a href="{DASHBOARD_URL}">← Use Dashboard Instead</a>
            </div>
        </div>
    </body>
    </html>
    """


@router.get("/complete")
async def complete_action(token: str = Query(...)):
    """Mark a notification as completed via magic link."""
    is_valid, payload, error = verify_action_token(token)
    
    if not is_valid:
        return HTMLResponse(content=error_page("Link Invalid", error), status_code=400)
    
    notification_id = payload.get("notification_id")
    
    # Get current status to check if already processed
    notifications = db_service.get_staff_notifications()
    notification = next((n for n in notifications if n.get("$id") == notification_id), None)
    
    if not notification:
        return HTMLResponse(content=error_page("Not Found", "This notification no longer exists. It may have been archived."), status_code=404)
    
    current_status = notification.get("status", "pending")
    
    # Check if already processed
    if current_status == "completed":
        return HTMLResponse(content=success_page(
            "✅ Already Complete",
            "This callback was already marked as completed. No action needed."
        ))
    
    if current_status == "archived":
        return HTMLResponse(content=error_page("Archived", "This notification was archived. Please use the dashboard to restore it if needed."), status_code=400)
    
    # Update the notification
    result = db_service.update_staff_notification(notification_id, {"status": "completed"})
    
    if not result:
        return HTMLResponse(content=error_page("Update Failed", "Could not update the notification. Please try the dashboard instead."), status_code=400)
    
    logger.info(f"Magic link: Marked {notification_id} as completed")
    return HTMLResponse(content=success_page(
        "✅ Marked Complete",
        "The callback request has been marked as completed."
    ))


@router.get("/dismiss")
async def dismiss_action(token: str = Query(...)):
    """Dismiss a notification via magic link."""
    is_valid, payload, error = verify_action_token(token)
    
    if not is_valid:
        return HTMLResponse(content=error_page("Link Invalid", error), status_code=400)
    
    notification_id = payload.get("notification_id")
    
    # Get current status to check if already processed
    notifications = db_service.get_staff_notifications()
    notification = next((n for n in notifications if n.get("$id") == notification_id), None)
    
    if not notification:
        return HTMLResponse(content=error_page("Not Found", "This notification no longer exists."), status_code=404)
    
    current_status = notification.get("status", "pending")
    
    # Check if already processed
    if current_status == "dismissed":
        return HTMLResponse(content=success_page(
            "✅ Already Dismissed",
            "This notification was already dismissed. No action needed."
        ))
    
    if current_status == "completed":
        return HTMLResponse(content=error_page("Already Completed", "This callback was already completed. You can't dismiss it now."), status_code=400)
    
    if current_status == "archived":
        return HTMLResponse(content=error_page("Archived", "This notification was archived."), status_code=400)
    
    result = db_service.update_staff_notification(notification_id, {"status": "dismissed"})
    
    if not result:
        return HTMLResponse(content=error_page("Update Failed", "Could not dismiss the notification."), status_code=400)
    
    logger.info(f"Magic link: Dismissed {notification_id}")
    return HTMLResponse(content=success_page(
        "✅ Dismissed",
        "The notification has been dismissed."
    ))


@router.get("/reject")
async def reject_action(token: str = Query(...)):
    """
    Reject a booking/request - shows phone dialer to call customer.
    """
    is_valid, payload, error = verify_action_token(token)
    
    if not is_valid:
        return HTMLResponse(content=error_page("Link Invalid", error), status_code=400)
    
    notification_id = payload.get("notification_id")
    
    # Get the notification to find customer phone
    notifications = db_service.get_staff_notifications()
    notification = next((n for n in notifications if n.get("$id") == notification_id), None)
    
    if not notification:
        return HTMLResponse(content=error_page("Not Found", "Could not find this notification."), status_code=404)
    
    customer_phone = notification.get("customerPhone", notification.get("customer_phone", ""))
    customer_name = notification.get("customerName", notification.get("customer_name", "Customer"))
    
    # Update notification status to rejected
    db_service.update_staff_notification(notification_id, {"status": "rejected"})
    
    # Also update reservation status to 'cancelled'
    import json
    extra_data_str = notification.get("extra_data", "{}")
    try:
        extra_data = json.loads(extra_data_str) if isinstance(extra_data_str, str) else extra_data_str
    except:
        extra_data = {}
    
    booking_reference = extra_data.get("booking_reference", "")
    if booking_reference:
        import requests
        from core.config import settings
        MOTEL_DB_ID = "6947b8300005f5863f96"
        
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
                    json={"data": {"status": "cancelled"}}
                )
                if patch_response.status_code in [200, 201]:
                    logger.info(f"❌ Updated reservation {booking_reference} status to 'cancelled'")
    
    # Show page with call button
    return HTMLResponse(content=success_page(
        "📞 Call Customer",
        f"Please call {customer_name} to explain the rejection.",
        phone=customer_phone
    ))


@router.get("/update")
async def update_action(token: str = Query(...)):
    """Redirect to dashboard for manual update."""
    is_valid, payload, error = verify_action_token(token)
    
    if not is_valid:
        return HTMLResponse(content=error_page("Link Invalid", error), status_code=400)
    
    notification_id = payload.get("notification_id")
    
    # Mark as in_progress
    db_service.update_staff_notification(notification_id, {"status": "in_progress"})
    
    # Redirect to dashboard
    return RedirectResponse(url=f"{DASHBOARD_URL}?highlight={notification_id}")


@router.get("/approve")
async def approve_action(token: str = Query(...)):
    """
    Approve a booking request - updates status and sends guest confirmation.
    """
    is_valid, payload, error = verify_action_token(token)
    
    if not is_valid:
        return HTMLResponse(content=error_page("Link Invalid", error), status_code=400)
    
    notification_id = payload.get("notification_id")
    
    # Get notification with booking data
    notifications = db_service.get_staff_notifications()
    notification = next((n for n in notifications if n.get("$id") == notification_id), None)
    
    if not notification:
        return HTMLResponse(content=error_page("Not Found", "This notification no longer exists."), status_code=404)
    
    # Check if already processed
    current_status = notification.get("status", "pending")
    if current_status == "completed":
        return HTMLResponse(content=success_page(
            "✅ Already Approved",
            "This booking was already approved."
        ))
    
    # Mark as completed (approved)
    result = db_service.update_staff_notification(notification_id, {
        "status": "completed",
        "staff_notes": "Approved via email"
    })
    
    if not result:
        return HTMLResponse(content=error_page("Update Failed", "Could not approve. Please use the dashboard."), status_code=400)
    
    # Also update the reservation status to 'confirmed'
    import json
    extra_data_str = notification.get("extra_data", "{}")
    try:
        extra_data = json.loads(extra_data_str) if isinstance(extra_data_str, str) else extra_data_str
    except:
        extra_data = {}
    
    booking_reference = extra_data.get("booking_reference", "")
    if booking_reference:
        # Find and update reservation
        import requests
        from core.config import settings
        MOTEL_DB_ID = "6947b8300005f5863f96"
        
        headers = {
            "Content-Type": "application/json",
            "X-Appwrite-Project": settings.APPWRITE_PROJECT_ID,
            "X-Appwrite-Key": settings.APPWRITE_API_KEY
        }
        
        # Find reservation by booking_reference
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
                    logger.info(f"✅ Updated reservation {booking_reference} status to 'confirmed'")
                else:
                    logger.warning(f"Failed to update reservation status: {patch_response.text}")
    
    # Send guest confirmation email if we have guest email in extra_data
    import json
    extra_data_str = notification.get("extra_data", "{}")
    try:
        extra_data = json.loads(extra_data_str) if isinstance(extra_data_str, str) else extra_data_str
    except:
        extra_data = {}
    
    guest_email = extra_data.get("guest_email", "")
    if guest_email:
        import asyncio
        from services.email import email_service
        asyncio.create_task(
            email_service.send_guest_booking_confirmation(
                guest_email=guest_email,
                guest_name=notification.get("customer_name", "Guest"),
                booking_reference=extra_data.get("booking_reference", ""),
                room_type=extra_data.get("room_type", "queen"),
                check_in=extra_data.get("check_in", ""),
                check_out=extra_data.get("check_out", ""),
                num_nights=extra_data.get("num_nights", 1),
                total_amount=extra_data.get("total_amount", 0)
            )
        )
        logger.info(f"Magic link: Approved booking, sending confirmation to {guest_email}")
        
        return HTMLResponse(content=success_page(
            "✅ Booking Approved",
            f"The booking has been approved and a confirmation email has been sent to {guest_email}."
        ))
    else:
        logger.info(f"Magic link: Approved booking (no guest email)")
        return HTMLResponse(content=success_page(
            "✅ Booking Approved",
            "The booking has been approved. No guest email was provided, so please contact them directly."
        ))
