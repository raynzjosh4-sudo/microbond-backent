import logging
import time
from sqlmodel import Session, select
from app.core.database import engine
from app.models.group.finance import MemberObligation, GroupPenalty
from app.models.group.settings import GroupFinancialSettings

logger = logging.getLogger(__name__)

def process_late_penalties_and_grace_periods():
    """
    Cron Job that checks for overdue obligations.
    It respects the Grace Period setting. If the Grace Period has expired,
    it marks the obligation as LATE and applies the Late Fee Penalty.
    """
    now_ms = int(time.time() * 1000)
    with Session(engine) as session:
        # Find all pending obligations that are past their due date
        overdue_obligations = session.exec(
            select(MemberObligation).where(
                MemberObligation.status == "PENDING",
                MemberObligation.amount_paid < MemberObligation.amount_due,
                MemberObligation.due_date < now_ms
            )
        ).all()
        
        if not overdue_obligations:
            return
            
        logger.info(f"Penalty Processor: Checking {len(overdue_obligations)} potentially late obligations.")
        
        # Cache financial settings to avoid repetitive queries
        settings_cache = {}
        
        for ob in overdue_obligations:
            if ob.group_id not in settings_cache:
                settings = session.exec(select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == ob.group_id)).first()
                settings_cache[ob.group_id] = settings
                
            fin_settings = settings_cache.get(ob.group_id)
            if not fin_settings:
                continue
                
            # 1. Grace Period Math
            grace_period_ms = 0
            if fin_settings.enable_grace_period:
                grace_period_ms = fin_settings.grace_period_hours * 3600000
                
            cutoff_time = ob.due_date + grace_period_ms
            
            # 2. Check if truly late (past grace period)
            if now_ms > cutoff_time:
                ob.status = "LATE"
                session.add(ob)
                
                # 3. Apply Late Fee Penalty
                if fin_settings.enable_late_fees:
                    # Make sure we haven't already applied a penalty for this exact obligation
                    existing_penalty = session.exec(
                        select(GroupPenalty).where(GroupPenalty.obligation_id == ob.id)
                    ).first()
                    
                    if not existing_penalty:
                        penalty = GroupPenalty(
                            group_id=ob.group_id,
                            user_id=ob.user_id,
                            obligation_id=ob.id,
                            penalty_amount=fin_settings.late_fee_amount,
                            reason=f"Late fee for Cycle {ob.cycle_number} (Missed Due Date: {time.strftime('%Y-%m-%d', time.gmtime(ob.due_date/1000))})"
                        )
                        session.add(penalty)
                        logger.info(f"Applied {fin_settings.late_fee_amount} penalty to User {ob.user_id} for Obligation {ob.id}")

        session.commit()
        logger.info("Finished processing late penalties and grace periods.")
