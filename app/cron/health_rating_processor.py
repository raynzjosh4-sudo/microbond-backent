import logging
from sqlmodel import Session, select
from app.core.database import engine
from app.models.group.group import Group
from app.models.group.finance import MemberObligation, GroupPenalty
from app.models.group.settings import GroupFinancialSettings
import time

logger = logging.getLogger(__name__)

def process_daily_health_ratings():
    """
    Cron Job that wakes up to recalculate the health grade of all active groups.
    It counts obligations and updates the static health_grade columns in the Group table.
    """
    with Session(engine) as session:
        # Get all ACTIVE groups
        active_groups = session.exec(
            select(Group).where(Group.status == "ACTIVE")
        ).all()
        
        if not active_groups:
            return
            
        logger.info(f"Health Processor woke up: Processing {len(active_groups)} groups.")
        
        for group in active_groups:
            try:
                # Get all obligations for this group
                obligations = session.exec(
                    select(MemberObligation).where(MemberObligation.group_id == group.group_id)
                ).all()
                
                total_obligations = len(obligations)
                if total_obligations == 0:
                    group.health_grade = "A+"
                    group.on_time_repayment_rate_pct = 100.0
                    group.active_default_rate_pct = 0.0
                    session.add(group)
                    continue
                    
                on_time_count = sum(1 for o in obligations if o.status == "PAID")
                default_count = sum(1 for o in obligations if o.status == "DEFAULTED")
                late_count = sum(1 for o in obligations if o.status == "LATE")
                
                completed_obligations = on_time_count + late_count + default_count
                
                if completed_obligations > 0:
                    on_time_percentage = (on_time_count / completed_obligations) * 100
                    default_percentage = (default_count / completed_obligations) * 100
                else:
                    on_time_percentage = 100.0
                    default_percentage = 0.0
                    
                # Determine Grade based on stats
                grade = "A+"
                
                if default_percentage > 10:
                    grade = "D"
                elif default_percentage > 0 or on_time_percentage < 80:
                    grade = "C"
                elif on_time_percentage < 95:
                    grade = "B"
                    
                # Update group fields
                group.health_grade = grade
                group.on_time_repayment_rate_pct = on_time_percentage
                group.active_default_rate_pct = default_percentage
                
                session.add(group)
                
            except Exception as e:
                logger.error(f"Error processing health rating for group {group.group_id}: {str(e)}")
                
        # Commit all updates
        session.commit()
        logger.info("Finished processing health ratings.")

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
