from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .helpers import get_campaign, require_member, now_ms

router = APIRouter()

@router.get("/{group_id}/dashboard", summary="View campaign status and stats")
def get_fundraiser_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the full campaign picture: locked config + live stats + calculated progress.
    Any active member of the group can view this.
    """
    require_member(group_id, current_user, session)
    config, stats = get_campaign(group_id, session)

    # Calculate progress percentage
    if config.target_amount > 0:
        progress_pct = round((stats.total_raised / config.target_amount) * 100, 2)
    else:
        progress_pct = None  # open-ended, no target to measure against

    # Calculate days remaining
    if config.campaign_deadline:
        ms_remaining = config.campaign_deadline - now_ms()
        days_remaining = max(0, ms_remaining // (1000 * 60 * 60 * 24))
    else:
        days_remaining = None

    return {
        "status": "success",
        "data": {
            "campaign_config": config.model_dump(mode="json"),
            "live_stats": stats.model_dump(mode="json"),
            "progress_percentage": progress_pct,
            "days_remaining": days_remaining
        }
    }
