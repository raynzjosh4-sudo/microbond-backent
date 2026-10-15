from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import UpdateFundraiserSettingsRequest
from .helpers import get_campaign, require_admin, now_ms

router = APIRouter()

@router.patch("/{group_id}/settings", summary="Update campaign settings")
def update_fundraiser_settings(
    group_id: str,
    request: UpdateFundraiserSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin updates the mutable campaign settings (FundraiserLiveStats fields only).
    Locked config fields (target, deadline, payout destination) cannot be changed.
    """
    require_admin(group_id, current_user, session)
    _, stats = get_campaign(group_id, session)

    if stats.is_paid_out:
        raise HTTPException(status_code=400, detail="Cannot update settings for a fundraiser that has already paid out.")

    if request.allow_overfunding is not None:
        stats.allow_overfunding = request.allow_overfunding
    if request.stop_on_target_reached is not None:
        stats.stop_on_target_reached = request.stop_on_target_reached
    if request.minimum_donation_amount is not None:
        stats.minimum_donation_amount = request.minimum_donation_amount

    stats.updated_at = now_ms()
    session.add(stats)
    session.commit()
    session.refresh(stats)

    return {
        "status": "success",
        "message": "Fundraiser settings updated.",
        "data": stats.model_dump(mode="json")
    }
