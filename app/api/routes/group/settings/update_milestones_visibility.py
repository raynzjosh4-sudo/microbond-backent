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


class UpdateMilestoneVisibilityRequest(BaseModel):
    vis_share_financial_snapshots: Optional[bool] = None
    vis_announce_system_events: Optional[bool] = None
    vis_post_security_rule_updates: Optional[bool] = None
    vis_post_group_approval_polls: Optional[bool] = None
    vis_post_loan_approval_polls: Optional[bool] = None
    vis_notify_important_rule_changes: Optional[bool] = None
    notify_important_rule_changes: Optional[bool] = None


@router.patch("/{group_id}/settings/milestones-visibility", summary="Admin: Update Milestones & Security Visibility")
def update_milestones_visibility_settings(
    group_id: str,
    request: UpdateMilestoneVisibilityRequest,
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

    if request.vis_share_financial_snapshots is not None:
        settings.vis_share_financial_snapshots = request.vis_share_financial_snapshots
    if request.vis_announce_system_events is not None:
        settings.vis_announce_system_events = request.vis_announce_system_events
    if request.vis_post_security_rule_updates is not None:
        settings.vis_post_security_rule_updates = request.vis_post_security_rule_updates
    if request.vis_post_group_approval_polls is not None:
        settings.vis_post_group_approval_polls = request.vis_post_group_approval_polls
    if request.vis_post_loan_approval_polls is not None:
        settings.vis_post_loan_approval_polls = request.vis_post_loan_approval_polls

    rule_change_val = request.vis_notify_important_rule_changes if request.vis_notify_important_rule_changes is not None else request.notify_important_rule_changes
    if rule_change_val is not None:
        settings.vis_notify_important_rule_changes = rule_change_val
        settings.notify_important_rule_changes = rule_change_val

    session.add(settings)
    session.commit()

    return {"status": "success", "message": "Milestones and Security visibility updated successfully."}
