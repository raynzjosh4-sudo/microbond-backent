import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import UpdateInvestmentClubSettingsRequest
from .helpers import require_admin, get_club, now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.patch("/{group_id}/settings", summary="Admin updates mutable club settings")
def update_investment_club_settings(
    group_id: str,
    request: UpdateInvestmentClubSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates mutable operational settings for the Investment Club:
    - minimum_purchase_quota
    - proposal_approval_threshold_pct
    - admin_management_fee_pct
    - allow_internal_share_transfers
    - enable_late_fees
    """
    require_admin(group_id, current_user, session)
    config, settings = get_club(group_id, session)

    update_dict = request.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid settings provided to update.")

    for field, val in update_dict.items():
        if hasattr(settings, field) and val is not None:
            setattr(settings, field, val)

    settings.updated_at = now_ms()
    session.add(settings)

    try:
        session.commit()
        session.refresh(settings)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error updating investment club settings: {e}")
        raise HTTPException(status_code=500, detail="Database error updating settings.")

    return {
        "status": "success",
        "message": "Investment club settings updated successfully.",
        "data": settings.model_dump(mode="json")
    }

