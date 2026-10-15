from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .helpers import get_welfare_fund, require_member, now_ms

router = APIRouter()

@router.get("/{group_id}/dashboard", summary="View Welfare Fund status, reserve balance, and claim eligibility")
def get_welfare_fund_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full state of the Welfare Fund:
    - Creation configuration rules (Table 1)
    - Live operational settings & counters (Table 2)
    - Calculated claimable balance & health status
    - Member claim eligibility status
    """
    member = require_member(group_id, current_user, session)
    config, settings = get_welfare_fund(group_id, session)
    current_time_ms = now_ms()

    # Calculate claimable pool
    claimable_balance = max(0, settings.current_balance - settings.minimum_reserve_balance)
    fund_health = "HEALTHY" if settings.current_balance >= settings.minimum_reserve_balance else "CRITICAL"

    # Member eligibility
    waiting_period_ms = config.waiting_period_days * 86400 * 1000
    member_eligible_at = member.joined_at + waiting_period_ms
    is_eligible = current_time_ms >= member_eligible_at
    waiting_days_remaining = max(0, int((member_eligible_at - current_time_ms) / (86400 * 1000))) if not is_eligible else 0

    return {
        "status": "success",
        "data": {
            "welfare_config": config.model_dump(mode="json"),
            "operational_settings": settings.model_dump(mode="json"),
            "claimable_balance": claimable_balance,
            "fund_health": fund_health,
            "member_claim_eligibility": {
                "is_eligible": is_eligible,
                "waiting_days_remaining": waiting_days_remaining,
                "waiting_period_days": config.waiting_period_days
            }
        }
    }
