import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.cronjobs.launcher.group_launcher import check_and_launch_pending_groups
from app.cronjobs.finance.late_fee_processor import process_daily_late_fees
from app.cronjobs.finance.payout_disbursement_worker import process_due_group_payouts
from app.cronjobs.health.daily_health_ratings import process_daily_health_ratings
from app.cronjobs.finance.collection_reminder_worker import process_collection_reminders
from app.cronjobs.finance.auto_debit_prompt_worker import process_auto_debit_prompts

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
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=30
    )

    # Run the automated group payout disbursement worker every 2 minutes
    scheduler.add_job(
        process_due_group_payouts,
        trigger=IntervalTrigger(minutes=2),
        id="process_group_payouts",
        name="Process Due Group Payout Disbursements",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60
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

    # Run the Collection Reminder Worker every 15 minutes
    scheduler.add_job(
        process_collection_reminders,
        trigger=IntervalTrigger(minutes=15),
        id="process_collection_reminders",
        name="Process Rotating Collection Reminders",
        replace_existing=True,
        coalesce=True
    )

    # Run the Auto-Debit Prompt Worker every 5 minutes
    scheduler.add_job(
        process_auto_debit_prompts,
        trigger=IntervalTrigger(minutes=5),
        id="process_auto_debit_prompts",
        name="Process Auto-Debit USSD Prompts",
        replace_existing=True,
        coalesce=True
    )
    
    scheduler.start()
    logger.info("APScheduler started: Cron Jobs running.")

