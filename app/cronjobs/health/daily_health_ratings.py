import logging
import time
import json
from sqlmodel import Session, select
from sqlalchemy import func
from app.core.database import engine
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation, GroupPayout
from app.models.group.health import GroupHealth
from app.core.microbond_core import calculate_batch_health_grades

logger = logging.getLogger(__name__)

def process_daily_health_ratings():
    """
    Cron Job that wakes up to recalculate the health grade of all active groups.
    It updates the metrics in the separate GroupHealth table using DB aggregations.
    """
    now_ms = int(time.time() * 1000)
    seven_days_ms = 7 * 24 * 60 * 60 * 1000

    with Session(engine) as session:
        active_groups = session.exec(select(Group).where(Group.status == "ACTIVE")).all()
        if not active_groups:
            return
            
        logger.info(f"Health Processor woke up: Processing {len(active_groups)} groups.")
        
        for group in active_groups:
            try:
                # 1. Fetch or create GroupHealth record
                health = session.exec(select(GroupHealth).where(GroupHealth.group_id == group.group_id)).first()
                if not health:
                    health = GroupHealth(group_id=group.group_id)

                # 2. Get Obligations via SQL Aggregation
                status_counts = session.exec(
                    select(MemberObligation.status, func.count(MemberObligation.id))
                    .where(MemberObligation.group_id == group.group_id)
                    .group_by(MemberObligation.status)
                ).all()
                counts = dict(status_counts)
                
                on_time_count = counts.get("PAID", 0)
                default_count = counts.get("DEFAULTED", 0)
                late_count = counts.get("LATE", 0)
                completed_obligations = on_time_count + late_count + default_count

                if completed_obligations > 0:
                    health.on_time_repayment_rate_pct = (on_time_count / completed_obligations) * 100.0
                    health.active_default_rate_pct = (default_count / completed_obligations) * 100.0
                else:
                    health.on_time_repayment_rate_pct = 100.0
                    health.active_default_rate_pct = 0.0

                health.total_defaulted_amount = session.exec(
                    select(func.sum(MemberObligation.amount_due - MemberObligation.amount_paid))
                    .where(MemberObligation.group_id == group.group_id, MemberObligation.status == "DEFAULTED")
                ).first() or 0.0
                
                # Unique members in arrears
                health.members_in_arrears_count = session.exec(
                    select(func.count(func.distinct(MemberObligation.user_id)))
                    .where(MemberObligation.group_id == group.group_id, MemberObligation.status.in_(["LATE", "DEFAULTED"]))
                ).first() or 0

                # 3. Liquidity Ratio (Group Balance vs Next 7 days payouts)
                upcoming_payout_sum = session.exec(
                    select(func.sum(GroupPayout.amount_expected))
                    .where(
                        GroupPayout.group_id == group.group_id,
                        GroupPayout.status == "PENDING",
                        GroupPayout.payout_date <= now_ms + seven_days_ms
                    )
                ).first() or 0.0
                
                if upcoming_payout_sum > 0:
                    health.liquidity_ratio = float(group.total_balance) / upcoming_payout_sum
                else:
                    health.liquidity_ratio = 1.0

                # 4. Average Member Trust Score & Active Member Count
                avg_score = session.exec(
                    select(func.avg(GroupMembership.group_trust_score))
                    .where(GroupMembership.group_id == group.group_id, GroupMembership.status == "ACTIVE")
                ).first()
                health.average_member_trust_score = float(avg_score) if avg_score else 100.0

                active_member_count = session.exec(
                    select(func.count(GroupMembership.id))
                    .where(GroupMembership.group_id == group.group_id, GroupMembership.status == "ACTIVE")
                ).first() or 1

                # 5. Determine Master Grade using Authoritative microbond_core Domain Engine
                batch_input = [
                    {
                        "group_id": group.group_id,
                        "on_time_count": on_time_count,
                        "late_count": late_count,
                        "default_count": default_count,
                        "total_defaulted_amount_minor": int(health.total_defaulted_amount),
                        "total_expected_amount_minor": int(upcoming_payout_sum or 1),
                        "members_in_arrears_count": health.members_in_arrears_count,
                        "total_active_members": active_member_count,
                    }
                ]
                grades_data = json.loads(calculate_batch_health_grades(batch_input))
                scored = grades_data[0] if grades_data else {"grade": "A+", "risk_tier": "LOW"}

                health.health_grade = scored["grade"]
                health.risk_level = scored["risk_tier"]
                health.last_recalculated_at = now_ms
                
                session.add(health)
                
            except Exception as e:
                logger.error(f"Error processing health rating for group {group.group_id}: {str(e)}")
                
        # Commit all updates
        session.commit()
        logger.info("Finished processing health ratings.")
