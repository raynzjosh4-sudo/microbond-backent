import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import UpdateEventCommitteeSettingsRequest
from .helpers import get_event_committee, require_admin, now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.patch("/{group_id}/settings", summary="Admin updates mutable operational settings")
def update_event_committee_settings(
    group_id: str,
    request: UpdateEventCommitteeSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates mutable operational settings for the Event Committee:
    - allow_overfunding
    - track_pledges
    - minimum_contribution_amount
    - member_quota_amount
    - allow_guest_deposits
    - allow_partial_disbursements
    - signoff_trustee_user_ids
    """
    require_admin(group_id, current_user, session)
    config, settings = get_event_committee(group_id, session)

    update_dict = request.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid settings provided to update.")

    for field, val in update_dict.items():
        if field == "signoff_trustee_user_ids" and val is not None:
            settings.signoff_trustee_user_ids = json.dumps(val)
        elif hasattr(settings, field) and val is not None:
            setattr(settings, field, val)

    settings.updated_at = now_ms()
    session.add(settings)

    try:
        session.commit()
        session.refresh(settings)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error updating event committee settings: {e}")
        raise HTTPException(status_code=500, detail="Database error updating settings.")

    return {
        "status": "success",
        "message": "Event Committee settings updated successfully.",
        "data": settings.model_dump(mode="json")
    }
