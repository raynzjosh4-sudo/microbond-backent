from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .helpers import get_event_committee, require_member, now_ms

router = APIRouter()

@router.get("/{group_id}/dashboard", summary="View Event Committee budget progress, pledges, and countdown")
def get_event_committee_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full state of the Event Committee:
    - Creation configuration rules (Table 1)
    - Live operational settings & counters (Table 2)
    - Budget progress percentage
    - Pledge fulfillment percentage
    - Countdown to collection deadline and event date
    """
    require_member(group_id, current_user, session)
    config, settings = get_event_committee(group_id, session)
    current_time_ms = now_ms()

    # Progress calculations
    budget_pct = None
    if config.event_target_budget > 0:
        budget_pct = round((settings.current_balance / config.event_target_budget) * 100, 2)

    pledge_fulfillment_pct = None
    if settings.total_pledged > 0:
        pledge_fulfillment_pct = round((settings.current_balance / settings.total_pledged) * 100, 2)

    days_to_deadline = max(0, int((config.collection_deadline - current_time_ms) / (86400 * 1000)))
    days_to_event = max(0, int((config.event_date - current_time_ms) / (86400 * 1000)))

    return {
        "status": "success",
        "data": {
            "event_config": config.model_dump(mode="json"),
            "operational_settings": settings.model_dump(mode="json"),
            "budget_progress_percentage": budget_pct,
            "pledge_fulfillment_percentage": pledge_fulfillment_pct,
            "days_to_deadline": days_to_deadline,
            "days_to_event": days_to_event,
            "net_available_balance": max(0, settings.current_balance)
        }
    }
