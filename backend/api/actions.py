"""
Magic Link Actions API
Handles email-based action links for staff operations (complete, dismiss, approve, reject).
"""
from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from services.magic_links import verify_action_token
from services.appwrite import db_service
import html
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actions", tags=["actions"])

# Every db_service notification method is `async def` (services/db/notifications.py).
# Calling them without `await` hands back a coroutine, so `next(... for n in
# notifications)` raised TypeError and every staff magic link 500'd while the
# update never ran. Each call below MUST be awaited.

# GET never acts; POST does. Mail security scanners and link previewers (Outlook
# Safe Links, Gmail, Slack/Teams unfurls) fetch every URL in an email on their own,
# so a GET that mutated could complete a callback, or approve/reject a booking and
# burn its one-time link, before any human clicked. The emailed URLs are still
# GETs (already-sent emails keep working): GET only verifies the token and renders
# a confirm page whose button POSTs the same token to the same path, where the
# token is verified again and the action runs. Bots follow links; they don't
# submit forms. GET must stay free of db_service calls.

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


def confirm_page(title: str, message: str, button: str, token: str) -> str:
    """
    Generate the confirm page a magic-link GET shows instead of acting.

    The form has no action attribute, so it POSTs back to the exact URL the email
    opened (same path, same ?token=), whatever prefix the router is mounted under.
    The token also rides in the body, which is what the POST routes read.
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="robots" content="noindex">
        <title>{title}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f7; margin: 0; padding: 40px 20px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; padding: 40px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            h1 {{ font-size: 24px; color: #1d1d1f; margin-bottom: 16px; }}
            p {{ color: #86868b; font-size: 16px; line-height: 1.6; }}
            .btn {{ display: inline-block; padding: 14px 28px; background: #0066cc; color: white; border: 0; border-radius: 30px; font-size: 16px; font-weight: 600; margin-top: 24px; cursor: pointer; }}
            .back-link {{ margin-top: 24px; }}
            .back-link a {{ color: #0066cc; text-decoration: none; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{title}</h1>
            <p>{message}</p>
            <form method="post">
                <input type="hidden" name="token" value="{html.escape(token, quote=True)}">
                <button type="submit" class="btn">{button}</button>
            </form>
            <div class="back-link">
                <a href="{DASHBOARD_URL}">← Open Dashboard</a>
            </div>
        </div>
    </body>
    </html>
    """


# Path -> (title, message, button) for each magic link's confirm page.
_CONFIRM_COPY = {
    "complete": ("Mark as complete?", "Mark this callback request as completed.", "Mark Complete"),
    "dismiss": ("Dismiss notification?", "Dismiss this notification without calling back.", "Dismiss"),
    "reject": ("Reject this booking?", "This cancels the reservation. The email link works once, so this can't be undone from email.", "Reject Booking"),
    "update": ("Open in dashboard?", "Mark this request as in progress and open it in the dashboard.", "Mark In Progress"),
    "approve": ("Approve this booking?", "This confirms the reservation and emails the guest their confirmation. The email link works once.", "Approve Booking"),
}

# The token sits in the URL: keep it out of caches and Referer headers, and stop
# the one-click form being framed by another site (clickjacking).
_CONFIRM_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
}


def _verify_for(action: str, token: str):
    """verify_action_token, plus: the token must have been issued for THIS action.

    Tokens carry the action they were minted for, but nothing compared it with
    the route, so the "approve" link from a staff email also worked when posted
    to /reject (and "complete" to "dismiss"). One email's links then decide any
    outcome for that notification, not just the one the button names.
    """
    is_valid, payload, error = verify_action_token(token)
    if is_valid and payload.get("action") != action:
        return False, payload, "This link is for a different action."
    return is_valid, payload, error


def _confirm_route(action: str):
    async def confirm(token: str = Query(...)):
        # Same verification as the POST, so a dead link says so up front. Nothing
        # else: no db reads, no writes, the one-time link is not consumed here.
        is_valid, _payload, error = _verify_for(action, token)
        if not is_valid:
            return HTMLResponse(content=error_page("Link Invalid", error), status_code=400)
        title, message, button = _CONFIRM_COPY[action]
        return HTMLResponse(content=confirm_page(title, message, button, token), headers=_CONFIRM_HEADERS)
    return confirm


for _action in _CONFIRM_COPY:
    router.add_api_route(f"/{_action}", _confirm_route(_action), methods=["GET"], name=f"confirm_{_action}")


@router.post("/complete")
async def complete_action(token: str = Form(...)):
    """Mark a notification as completed via magic link."""
    is_valid, payload, error = _verify_for("complete", token)
    
    if not is_valid:
        return HTMLResponse(content=error_page("Link Invalid", error), status_code=400)
    
    notification_id = payload.get("notification_id")
    
    # Get current status to check if already processed
    notifications = await db_service.get_staff_notifications()
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
    result = await db_service.update_staff_notification(notification_id, {"status": "completed"})
    
    if not result:
        return HTMLResponse(content=error_page("Update Failed", "Could not update the notification. Please try the dashboard instead."), status_code=400)
    
    logger.info(f"Magic link: Marked {notification_id} as completed")
    return HTMLResponse(content=success_page(
        "✅ Marked Complete",
        "The callback request has been marked as completed."
    ))


@router.post("/dismiss")
async def dismiss_action(token: str = Form(...)):
    """Dismiss a notification via magic link."""
    is_valid, payload, error = _verify_for("dismiss", token)
    
    if not is_valid:
        return HTMLResponse(content=error_page("Link Invalid", error), status_code=400)
    
    notification_id = payload.get("notification_id")
    
    # Get current status to check if already processed
    notifications = await db_service.get_staff_notifications()
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
    
    result = await db_service.update_staff_notification(notification_id, {"status": "dismissed"})
    
    if not result:
        return HTMLResponse(content=error_page("Update Failed", "Could not dismiss the notification."), status_code=400)
    
    logger.info(f"Magic link: Dismissed {notification_id}")
    return HTMLResponse(content=success_page(
        "✅ Dismissed",
        "The notification has been dismissed."
    ))


@router.post("/reject")
async def reject_action(token: str = Form(...)):
    """
    Reject a booking/request - shows phone dialer to call customer.
    Magic link is ONE-TIME USE ONLY. Subsequent clicks redirect to dashboard.
    """
    is_valid, payload, error = _verify_for("reject", token)
    
    if not is_valid:
        return HTMLResponse(content=error_page("Link Invalid", error), status_code=400)
    
    notification_id = payload.get("notification_id")
    
    # Get the notification to find customer phone
    notifications = await db_service.get_staff_notifications()
    notification = next((n for n in notifications if n.get("$id") == notification_id), None)
    
    if not notification:
        return HTMLResponse(content=error_page("Not Found", "Could not find this notification."), status_code=404)
    
    # Check if magic link already consumed (ONE-TIME USE)
    import json
    extra_data_str = notification.get("extra_data", "{}")
    try:
        extra_data = json.loads(extra_data_str) if isinstance(extra_data_str, str) else extra_data_str
    except:
        extra_data = {}
    
    if extra_data.get("link_consumed"):
        # Link was already used - show info page
        first_action = extra_data.get("first_action", "processed")
        return HTMLResponse(content=f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link Already Used</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f7; margin: 0; padding: 40px 20px; }}
        .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; padding: 40px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        h1 {{ font-size: 24px; color: #1d1d1f; margin-bottom: 16px; }}
        p {{ color: #86868b; font-size: 16px; line-height: 1.6; }}
        .action-badge {{ display: inline-block; padding: 6px 16px; background: #ef4444; color: white; border-radius: 20px; font-size: 14px; font-weight: 600; margin: 16px 0; }}
        .btn {{ display: inline-block; padding: 14px 28px; background: #0066cc; color: white; text-decoration: none; border-radius: 30px; font-weight: 600; margin-top: 24px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 Link Already Used</h1>
        <div class="action-badge">First action: {first_action.upper()}</div>
        <p>This email link has already been used. Each link can only be used once for security.</p>
        <p>To make changes, please use the dashboard.</p>
        <a href="{DASHBOARD_URL}" class="btn">Open Dashboard</a>
    </div>
</body>
</html>''')
    
    customer_phone = notification.get("customerPhone", notification.get("customer_phone", ""))
    customer_name = notification.get("customerName", notification.get("customer_name", "Customer"))
    
    # Mark link as consumed IMMEDIATELY
    extra_data["link_consumed"] = True
    extra_data["first_action"] = "rejected"
    extra_data["first_action_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Update notification status to rejected with consumed flag
    await db_service.update_staff_notification(notification_id, {
        "status": "rejected",
        "extra_data": json.dumps(extra_data)
    })
    
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


@router.post("/update")
async def update_action(token: str = Form(...)):
    """Redirect to dashboard for manual update."""
    is_valid, payload, error = _verify_for("update", token)
    
    if not is_valid:
        return HTMLResponse(content=error_page("Link Invalid", error), status_code=400)
    
    notification_id = payload.get("notification_id")
    
    # Mark as in_progress
    await db_service.update_staff_notification(notification_id, {"status": "in_progress"})
    
    # Redirect to dashboard. 303 so the browser follows with a GET; the default
    # 307 would re-POST the form to the dashboard page.
    return RedirectResponse(url=f"{DASHBOARD_URL}?highlight={notification_id}", status_code=303)


@router.post("/approve")
async def approve_action(token: str = Form(...)):
    """
    Approve a booking request - updates status and sends guest confirmation.
    Magic link is ONE-TIME USE ONLY. Subsequent clicks redirect to dashboard.
    """
    is_valid, payload, error = _verify_for("approve", token)
    
    if not is_valid:
        return HTMLResponse(content=error_page("Link Invalid", error), status_code=400)
    
    notification_id = payload.get("notification_id")
    
    # Get notification with booking data
    notifications = await db_service.get_staff_notifications()
    notification = next((n for n in notifications if n.get("$id") == notification_id), None)
    
    if not notification:
        return HTMLResponse(content=error_page("Not Found", "This notification no longer exists."), status_code=404)
    
    # Check if magic link already consumed (ONE-TIME USE)
    import json
    extra_data_str = notification.get("extra_data", "{}")
    try:
        extra_data = json.loads(extra_data_str) if isinstance(extra_data_str, str) else extra_data_str
    except:
        extra_data = {}
    
    if extra_data.get("link_consumed"):
        # Link was already used - show info page
        first_action = extra_data.get("first_action", "processed")
        return HTMLResponse(content=f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link Already Used</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f7; margin: 0; padding: 40px 20px; }}
        .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; padding: 40px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        h1 {{ font-size: 24px; color: #1d1d1f; margin-bottom: 16px; }}
        p {{ color: #86868b; font-size: 16px; line-height: 1.6; }}
        .action-badge {{ display: inline-block; padding: 6px 16px; background: #22c55e; color: white; border-radius: 20px; font-size: 14px; font-weight: 600; margin: 16px 0; }}
        .btn {{ display: inline-block; padding: 14px 28px; background: #0066cc; color: white; text-decoration: none; border-radius: 30px; font-weight: 600; margin-top: 24px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 Link Already Used</h1>
        <div class="action-badge">First action: {first_action.upper()}</div>
        <p>This email link has already been used. Each link can only be used once for security.</p>
        <p>To make changes, please use the dashboard.</p>
        <a href="{DASHBOARD_URL}" class="btn">Open Dashboard</a>
    </div>
</body>
</html>''')
    
    # Mark link as consumed IMMEDIATELY (before any action)
    extra_data["link_consumed"] = True
    extra_data["first_action"] = "approved"
    extra_data["first_action_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Mark as completed (approved)
    result = await db_service.update_staff_notification(notification_id, {
        "status": "completed",
        "staff_notes": "Approved via email",
        "extra_data": json.dumps(extra_data)
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
