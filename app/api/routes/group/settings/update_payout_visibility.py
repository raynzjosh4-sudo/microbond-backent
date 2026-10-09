from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupVisibilitySettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdatePayoutVisibilityRequest(BaseModel):
    vis_manage_payout_order: Optional[bool] = None
    vis_late_fee_penalties: Optional[bool] = None
    vis_grace_period_window: Optional[bool] = None
    vis_enforce_payout_holds: Optional[bool] = None
    vis_substitute_member_allowance: Optional[bool] = None

@router.patch("/{group_id}/settings/payout-visibility", summary="Admin: Update Payout Rules Visibility")
def update_payout_visibility_settings(
    group_id: str, 
    request: UpdatePayoutVisibilityRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()
    
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update visibility settings.")

    settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Visibility settings not found.")

    if request.vis_manage_payout_order is not None:
        settings.vis_manage_payout_order = request.vis_manage_payout_order
    if request.vis_late_fee_penalties is not None:
        settings.vis_late_fee_penalties = request.vis_late_fee_penalties
    if request.vis_grace_period_window is not None:
        settings.vis_grace_period_window = request.vis_grace_period_window
    if request.vis_enforce_payout_holds is not None:
        settings.vis_enforce_payout_holds = request.vis_enforce_payout_holds
    if request.vis_substitute_member_allowance is not None:
        settings.vis_substitute_member_allowance = request.vis_substitute_member_allowance

    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Payout rules visibility settings updated successfully."}
