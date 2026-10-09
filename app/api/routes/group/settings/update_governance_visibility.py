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

class UpdateGovernanceVisibilityRequest(BaseModel):
    vis_multi_signature_roster: Optional[bool] = None
    vis_active_audit_status: Optional[bool] = None
    vis_approval_quorum: Optional[bool] = None
    vis_pending_payout_queue: Optional[bool] = None
    vis_require_multi_signature: Optional[bool] = None
    vis_time_lock_disbursals: Optional[bool] = None

@router.patch("/{group_id}/settings/governance-visibility", summary="Admin: Update Governance Rules Visibility")
def update_governance_visibility_settings(
    group_id: str, 
    request: UpdateGovernanceVisibilityRequest, 
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

    if request.vis_multi_signature_roster is not None:
        settings.vis_multi_signature_roster = request.vis_multi_signature_roster
    if request.vis_active_audit_status is not None:
        settings.vis_active_audit_status = request.vis_active_audit_status
    if request.vis_approval_quorum is not None:
        settings.vis_approval_quorum = request.vis_approval_quorum
    if request.vis_pending_payout_queue is not None:
        settings.vis_pending_payout_queue = request.vis_pending_payout_queue
    if request.vis_require_multi_signature is not None:
        settings.vis_require_multi_signature = request.vis_require_multi_signature
    if request.vis_time_lock_disbursals is not None:
        settings.vis_time_lock_disbursals = request.vis_time_lock_disbursals

    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Governance rules visibility settings updated successfully."}
