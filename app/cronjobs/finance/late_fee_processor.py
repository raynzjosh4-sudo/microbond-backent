import logging
from datetime import datetime, timezone
from sqlmodel import Session, select
from sqlalchemy.orm import with_polymorphic

from app.core.database import engine
from app.models.group.settings import GroupFinancialSettings
from app.models.group.finance import MemberObligation, GroupPenalty

logger = logging.getLogger(__name__)

def process_daily_late_fees():
    current_time_epoch = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    with Session(engine) as session:
        # Phase 1: Fetch IDs only, no locks yet
        overdue_ids = session.exec(
            select(MemberObligation.id).where(
                MemberObligation.status.in_(["PENDING", "LATE"]),
                MemberObligation.due_date < current_time_epoch
            )
        ).all()
        
    for ob_id in overdue_ids:
        # Phase 2: Process each obligation in its own atomic transaction
        try:
            with Session(engine) as session:
                # Lock exactly this row using SKIP LOCKED to prevent race conditions with user webhooks
                obligation = session.exec(
                    select(MemberObligation)
                    .where(MemberObligation.id == ob_id)
                    .with_for_update(skip_locked=True)
                ).first()
                
                if not obligation or obligation.status not in ["PENDING", "LATE"]:
                    continue # Someone else (or a webhook) already paid/processed this!
                
                settings = session.exec(select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == obligation.group_id)).first()
                if not settings:
                    continue
                    
                grace_ms = (settings.grace_period_hours * 3600000) if settings.enable_grace_period else 0
                cutoff_time = obligation.due_date + grace_ms
                default_cutoff_time = cutoff_time + (48 * 3600000) # escalate to DEFAULTED after 48 hours of being LATE
                
                if obligation.status == "PENDING" and current_time_epoch > cutoff_time:
                    obligation.status = "LATE"
                    logger.info(f"Obligation {obligation.id} marked LATE.")
                    
                elif obligation.status == "LATE" and current_time_epoch > default_cutoff_time:
                    obligation.status = "DEFAULTED"
                    logger.info(f"Obligation {obligation.id} escalated to DEFAULTED.")
                
                session.add(obligation)
                
                # Apply Penalty logic if late fees are enabled
                if settings.enable_late_fees and obligation.status in ["LATE", "DEFAULTED"]:
                    twenty_four_hours_ago = current_time_epoch - (24 * 3600000)
                    recent_penalty = session.exec(
                        select(GroupPenalty).where(
                            GroupPenalty.obligation_id == obligation.id,
                            GroupPenalty.created_at >= twenty_four_hours_ago
                        )
                    ).first()
                    
                    if not recent_penalty:
                        penalty = GroupPenalty(
                            group_id=obligation.group_id,
                            user_id=obligation.user_id,
                            obligation_id=obligation.id,
                            penalty_amount=settings.late_fee_amount,
                            reason=f"Late fee for missed payment on Obligation {obligation.id}"
                        )
                        session.add(penalty)
                
                # Commit immediately to release the row lock fast
                session.commit()
                
        except Exception as e:
            logger.error(f"Error processing obligation {ob_id}: {str(e)}")
