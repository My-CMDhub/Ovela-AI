"""
APScheduler Job Scheduler
==========================
Manages background scheduled jobs for Coal Creek CRM.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Create scheduler instance
scheduler = BackgroundScheduler(timezone=ZoneInfo("Australia/Melbourne"))


def start_scheduler():
    """
    Start the background scheduler and register all jobs.
    Called on application startup.
    """
    try:
        # Import jobs
        from .pending_nag import pending_nag_job
        from .pms_sync import sync_pms_sync_job
        
        # Register pending nag job (every 15 minutes)
        scheduler.add_job(
            pending_nag_job,
            trigger=CronTrigger(minute="*/15"),  # Every 15 minutes
            id="pending_nag_job",
            name="Pending Notification Nag",
            replace_existing=True
        )
        
        # Register PMS sync job (every 30 minutes)
        scheduler.add_job(
            sync_pms_sync_job,
            trigger=CronTrigger(minute="*/30"),  # Every 30 minutes
            id="pms_sync_job",
            name="PMS Sync (Update247)",
            replace_existing=True
        )
        
        # Start the scheduler
        scheduler.start()
        logger.info("✅ Scheduler started successfully")
        logger.info("📋 Registered jobs:")
        for job in scheduler.get_jobs():
            logger.info(f"   - {job.name} (ID: {job.id}, Next run: {job.next_run_time})")
    
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}", exc_info=True)


def shutdown_scheduler():
    """
    Gracefully shutdown the scheduler.
    Called on application shutdown.
    """
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("✅ Scheduler shut down successfully")
    except Exception as e:
        logger.error(f"❌ Error shutting down scheduler: {e}")


# For manual testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_scheduler()
    
    # Keep running
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown_scheduler()
