import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import UpdateAssociationDuesSettingsRequest
from .helpers import now_ms, require_admin, get_association

logger = logging.getLogger(__name__)

router = APIRouter()

@router.patch("/{group_id}/settings", summary="Admin updates mutable operational settings")
def update_association_settings(
    group_id: str,
    request: UpdateAssociationDuesSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates mutable operational settings for the Association:
    - auto_sweep_trigger
    - allow_advance_payments
    - grace_period_days
    - late_fee_amount
    - arrears_action
    - max_missed_cycles_allowed
    - show_defaulters_publicly
    - treasury_ledger_visibility
    """
    require_admin(group_id, current_user, session)
    config, settings = get_association(group_id, session)

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
        logger.exception(f"Error updating association settings: {e}")
        raise HTTPException(status_code=500, detail="Database error updating settings.")

    return {
        "status": "success",
        "message": "Association settings updated successfully.",
        "data": settings.model_dump(mode="json")
    }
