import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.cronjobs.launcher.group_launcher import check_and_launch_pending_groups
from app.cronjobs.finance.late_fee_processor import process_daily_late_fees
from app.cronjobs.health.daily_health_ratings import process_daily_health_ratings

logger = logging.getLogger(__name__)

def start_scheduler():
    """
    Initializes the BackgroundScheduler and starts the cron jobs.
    """
    scheduler = BackgroundScheduler()
    
    # Run the auto-launcher every 1 minute
    scheduler.add_job(
        check_and_launch_pending_groups,
        trigger=IntervalTrigger(minutes=1),
        id="auto_launch_groups",
        name="Check and launch pending groups",
        replace_existing=True
    )
    
    # Run the Late Fee Processor daily (every 24 hours). We'll set it to 1 hour for safety to catch any new missed obligations that day.
    scheduler.add_job(
        process_daily_late_fees,
        trigger=IntervalTrigger(hours=1),
        id="process_late_fees",
        name="Process Daily Late Fees",
        replace_existing=True
    )
    
    # Run the Health Rating Processor daily
    scheduler.add_job(
        process_daily_health_ratings,
        trigger=IntervalTrigger(hours=6),
        id="process_health_ratings",
        name="Process Group Health Ratings",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("APScheduler started: Cron Jobs running.")
