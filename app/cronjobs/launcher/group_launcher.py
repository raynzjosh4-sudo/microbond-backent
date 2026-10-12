import logging
from datetime import datetime
from sqlmodel import Session

from app.core.database import engine
from app.models.group.group import Group
from app.models.group.rotating import RotatingGroupDetails
from app.services.group.launcher_service import execute_group_launch

logger = logging.getLogger(__name__)

def check_and_launch_pending_groups():
    """
    Cron Job that wakes up to launch groups that have reached their start time.
    """
    current_time_epoch = int(datetime.utcnow().timestamp())
    
    try:
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
    except Exception as e:
        logger.warning(f"Auto-launcher skipped cycle (database unreachable or timing out): {e}")

