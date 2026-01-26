"""
PMS Background Sync Job
========================
Periodic sync from external PMS (Update247) to Ovela CRM.

Syncs:
- External bookings (website, walk-in) to dashboard
- Room availability status

Does NOT sync:
- AI-initiated bookings (staff manually adds to PMS)
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List

logger = logging.getLogger(__name__)

COALCREEK_TZ = ZoneInfo("Australia/Melbourne")


async def pms_sync_job():
    """
    Sync external bookings from PMS to Ovela CRM.
    
    Runs every 30 minutes (configurable).
    Imports website/walk-in bookings so staff sees unified view.
    """
    try:
        logger.info("🔄 Running PMS sync job...")
        
        from services.pms import get_pms_client, is_pms_configured
        from services.appwrite import db_service
        
        # Check if PMS is configured
        if not is_pms_configured("coalcreek"):
            logger.info("⏭️  PMS sync skipped - not configured")
            return
        
        pms = get_pms_client("coalcreek")
        if not pms:
            return
        
        # 1. Get bookings from PMS (last 7 days to 30 days ahead)
        from_date = (datetime.now(COALCREEK_TZ) - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = (datetime.now(COALCREEK_TZ) + timedelta(days=30)).strftime("%Y-%m-%d")
        
        pms_bookings = await pms.get_bookings(from_date=from_date, to_date=to_date)
        
        if not pms_bookings:
            logger.info("✅ No bookings to sync from PMS")
            return
        
        # 2. Get existing Ovela reservations
        ovela_reservations = db_service.get_reservations(limit=500)
        existing_refs = {r.get("booking_reference") for r in ovela_reservations if r.get("booking_reference")}
        existing_pms_ids = {r.get("pms_id") for r in ovela_reservations if r.get("pms_id")}
        
        # 3. Find new bookings (in PMS but not in Ovela)
        new_count = 0
        for booking in pms_bookings:
            # Skip if already exists
            if booking.reference in existing_refs:
                continue
            if booking.pms_id and booking.pms_id in existing_pms_ids:
                continue
            
            # Skip AI-initiated bookings (those should already be in Ovela)
            if booking.source == "ai":
                continue
            
            # Import external booking
            try:
                db_service.create_reservation({
                    "booking_reference": booking.reference,
                    "guest_name": booking.guest_name,
                    "guest_phone": booking.guest_phone,
                    "guest_email": booking.guest_email,
                    "check_in_date": booking.check_in,
                    "check_out_date": booking.check_out,
                    "room_type": booking.room_type,
                    "status": booking.status,
                    "source": booking.source,
                    "total_amount": booking.total_amount,
                    "pms_id": booking.pms_id,
                    "synced_from_pms": True,
                    "synced_at": datetime.now(COALCREEK_TZ).isoformat(),
                })
                new_count += 1
                logger.info(f"📥 Imported booking {booking.reference} from PMS ({booking.source})")
            except Exception as e:
                logger.error(f"❌ Failed to import booking {booking.reference}: {e}")
        
        # 4. Update room availability cache (optional enhancement)
        # room_status = await pms.get_room_status()
        # cache_availability(room_status)
        
        if new_count > 0:
            logger.info(f"✅ PMS sync complete: {new_count} new bookings imported")
        else:
            logger.info("✅ PMS sync complete: No new bookings")
    
    except Exception as e:
        logger.error(f"❌ PMS sync job failed: {e}", exc_info=True)


def sync_pms_sync_job():
    """
    Synchronous wrapper for the PMS sync job.
    Required for APScheduler which doesn't support async by default.
    """
    import asyncio
    
    try:
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(pms_sync_job())
    except Exception as e:
        logger.error(f"❌ PMS sync wrapper error: {e}")


if __name__ == "__main__":
    # Manual testing
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(pms_sync_job())
