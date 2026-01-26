"""
Pending Notification Nag Job
=============================
Checks for stale pending notifications (>30 mins) and sends aggressive SMS alerts to staff.

This implements the "Ghosting Prevention" strategy from edge_cases_strategy.md.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from services.appwrite import db_service
from services.sms import sms_service
from services.tenants.coalcreek.config import STAFF_PHONE

logger = logging.getLogger(__name__)

# Configuration
STALE_THRESHOLD_MINUTES = 30
MAX_NAGS_PER_NOTIFICATION = 3
COALCREEK_TZ = ZoneInfo("Australia/Melbourne")


def pending_nag_job():
    """
    Check for pending notifications older than 30 minutes and send SMS nags to staff.
    
    This job runs every 15 minutes to ensure staff don't ghost guests.
    """
    try:
        logger.info("🔍 Running pending nag job...")
        
        # Get all pending notifications
        notifications = db_service.get_staff_notifications(status="pending", limit=100)
        
        if not notifications:
            logger.info("✅ No pending notifications found")
            return
        
        now = datetime.now(COALCREEK_TZ)
        nag_count = 0
        
        for notification in notifications:
            # Parse creation time
            created_at_str = notification.get("$createdAt")
            if not created_at_str:
                continue
            
            try:
                # Appwrite returns ISO format with timezone
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                created_at = created_at.astimezone(COALCREEK_TZ)
            except Exception as e:
                logger.error(f"Failed to parse created_at for notification {notification.get('$id')}: {e}")
                continue
            
            # Calculate age
            age = now - created_at
            age_minutes = age.total_seconds() / 60
            
            if age_minutes < STALE_THRESHOLD_MINUTES:
                # Not stale yet
                continue
            
            # Check if we've already nagged too many times
            staff_notes = notification.get("staff_notes", "")
            nag_attempts = staff_notes.count("AUTO-NAG:")
            
            if nag_attempts >= MAX_NAGS_PER_NOTIFICATION:
                logger.info(f"⏭️  Skipping notification {notification.get('$id')} - already nagged {nag_attempts} times")
                continue
            
            # This notification is stale and needs a nag
            notification_id = notification.get("$id")
            customer_name = notification.get("customer_name", "Unknown")
            customer_phone = notification.get("customer_phone", "N/A")
            reason = notification.get("reason", "No reason provided")
            
            # Build aggressive SMS
            age_hours = int(age_minutes // 60)
            age_mins = int(age_minutes % 60)
            
            if age_hours > 0:
                age_str = f"{age_hours}h {age_mins}m"
            else:
                age_str = f"{age_mins} minutes"
            
            sms_message = f"""🚨 ACTION REQUIRED 🚨
Notification #{notification_id[:8]}
Guest: {customer_name}
Phone: {customer_phone}
Reason: {reason}

PENDING FOR {age_str}!
Please respond immediately.
"""
            
            # Send SMS to staff
            success = sms_service.send_sms(STAFF_PHONE, sms_message)
            
            if success:
                # Update notification with nag attempt
                new_notes = f"{staff_notes}\n[{now.strftime('%Y-%m-%d %H:%M')}] AUTO-NAG: Pending >{int(age_minutes)}min (Attempt #{nag_attempts + 1})".strip()
                
                db_service.update_staff_notification(notification_id, {
                    "urgency": "critical",
                    "staff_notes": new_notes
                })
                
                nag_count += 1
                logger.warning(f"📢 Sent nag SMS for notification {notification_id} (pending {age_str})")
            else:
                logger.error(f"❌ Failed to send nag SMS for notification {notification_id}")
        
        if nag_count > 0:
            logger.warning(f"🚨 Sent {nag_count} nag SMS(s) to staff")
        else:
            logger.info("✅ No stale notifications requiring nags")
    
    except Exception as e:
        logger.error(f"❌ Error in pending_nag_job: {e}", exc_info=True)


if __name__ == "__main__":
    # For manual testing
    logging.basicConfig(level=logging.INFO)
    pending_nag_job()
