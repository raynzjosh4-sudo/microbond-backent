import time
from sqlmodel import Session, select
from app.models.group.finance import GroupPayout
from app.models.group.settings import GroupFinancialSettings

def is_payout_queue_full(session: Session, group_id: str) -> bool:
    """
    Checks if the group has reached its max_pending_payouts limit.
    Returns True if the queue is full, meaning the group must freeze cycle progression.
    Returns False if there is still room in the queue to process the next payout.
    """
    settings = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    
    if not settings:
        return False
        
    limit = settings.max_pending_payouts
    
    current_time_ms = int(time.time() * 1000)
    
    # We count payouts that are "stuck" in the active queue:
    # They are PENDING, PROCESSING, or ON_HOLD
    # AND their scheduled payout date has already arrived.
    # (We ignore future cycles because they haven't entered the queue yet).
    stuck_payouts_stmt = select(GroupPayout).where(
        GroupPayout.group_id == group_id,
        GroupPayout.status.in_(["PENDING", "PROCESSING", "ON_HOLD"]),
        GroupPayout.payout_date <= current_time_ms
    )
    
    stuck_payouts = session.exec(stuck_payouts_stmt).all()
    
    return len(stuck_payouts) >= limit
