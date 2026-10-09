import logging
from datetime import datetime, timezone
from sqlmodel import Session, select

from app.core.database import engine
from app.models.group.settings import GroupFinancialSettings
from app.models.group.finance import MemberObligation, GroupPenalty

logger = logging.getLogger(__name__)

def process_daily_late_fees():
    """
    Cron Job that wakes up daily to process late fees.
    For every PENDING obligation that is past its due date, it marks it as LATE.
    For every LATE obligation, it checks if a penalty was already applied today.
    If not, and late fees are enabled, it adds a GroupPenalty.
    """
    current_time_epoch = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    with Session(engine) as session:
        # 1. Find all PENDING obligations that are past due and mark them LATE
        overdue_stmt = select(MemberObligation).where(
            MemberObligation.status == "PENDING",
            MemberObligation.due_date < current_time_epoch
        )
        overdue_obligations = session.exec(overdue_stmt).all()
        for obligation in overdue_obligations:
            obligation.status = "LATE"
            session.add(obligation)
            logger.info(f"Obligation {obligation.id} marked as LATE.")
        
        session.commit()
        
        # 2. Find all LATE obligations
        late_stmt = select(MemberObligation).where(MemberObligation.status == "LATE")
        late_obligations = session.exec(late_stmt).all()
        
        for obligation in late_obligations:
            try:
                # Check Group Financial Settings
                settings = session.exec(
                    select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == obligation.group_id)
                ).first()
                
                if not settings or not settings.enable_late_fees:
                    continue
                    
                # Check if grace period applies
                if settings.enable_grace_period:
                    grace_ms = settings.grace_period_hours * 60 * 60 * 1000
                    if current_time_epoch < (obligation.due_date + grace_ms):
                        # Still in grace period
                        continue
                        
                # Ensure we only apply one penalty per day (per 24 hours)
                twenty_four_hours_ago = current_time_epoch - (24 * 60 * 60 * 1000)
                recent_penalty_stmt = select(GroupPenalty).where(
                    GroupPenalty.obligation_id == obligation.id,
                    GroupPenalty.created_at >= twenty_four_hours_ago
                )
                recent_penalty = session.exec(recent_penalty_stmt).first()
                
                if not recent_penalty:
                    # Apply penalty!
                    penalty = GroupPenalty(
                        group_id=obligation.group_id,
                        user_id=obligation.user_id,
                        obligation_id=obligation.id,
                        penalty_amount=settings.late_fee_amount,
                        reason=f"Daily late fee penalty for missed Cycle {obligation.cycle_number} payment."
                    )
                    session.add(penalty)
                    logger.info(f"Applied daily late fee of {settings.late_fee_amount} to user {obligation.user_id} for obligation {obligation.id}")
            except Exception as e:
                logger.error(f"Error processing late fee for obligation {obligation.id}: {str(e)}")
                session.rollback()
                
        session.commit()
