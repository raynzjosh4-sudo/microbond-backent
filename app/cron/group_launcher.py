import logging
from datetime import datetime
from sqlmodel import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.database import engine
from app.models.group.group import Group
from app.models.group.rotating import RotatingGroupDetails
from app.services.group.launcher_service import execute_group_launch
from app.cron.late_fee_processor import process_daily_late_fees
from app.cron.health_rating_processor import process_daily_health_ratings

logger = logging.getLogger(__name__)

def check_and_launch_pending_groups():
    """
    Cron Job that wakes up to launch groups that have reached their start time.
    """
    current_time_epoch = int(datetime.utcnow().timestamp())
    
    with Session(engine) as session:
        # Find all groups that are PENDING and have reached their start time
        pending_groups = session.query(Group).join(RotatingGroupDetails, Group.group_id == RotatingGroupDetails.group_id).filter(
            Group.status == "PENDING",
            RotatingGroupDetails.is_payout_order_locked == False,
            RotatingGroupDetails.group_start_time <= current_time_epoch
        ).all()
        
        if not pending_groups:
            return
            
        logger.info(f"Auto-Launcher woke up: Found {len(pending_groups)} groups ready to launch.")
        
        for group in pending_groups:
            try:
                # Wrap each group launch in its own transaction sub-block (SAVEPOINT)
                session.begin_nested()
                success = execute_group_launch(session, group.group_id)
                if success:
                    logger.info(f"Successfully auto-launched group {group.group_id}")
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Error auto-launching group {group.group_id}: {str(e)}")
        
        # Commit all successful sub-transactions to the DB
        session.commit()

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
