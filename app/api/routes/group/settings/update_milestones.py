from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupCommunicationSettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateMilestoneSettingsRequest(BaseModel):
    share_financial_snapshots: Optional[bool] = None
    announce_system_events: Optional[bool] = None
    post_security_rule_updates: Optional[bool] = None
    post_group_approval_polls: Optional[bool] = None
    notify_important_rule_changes: Optional[bool] = None

@router.patch("/{group_id}/settings/milestones", summary="Admin: Update Milestones & Security Settings")
def update_milestone_settings(
    group_id: str, 
    request: UpdateMilestoneSettingsRequest, 
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
        raise HTTPException(status_code=403, detail="Only the Group Admin can update milestone and security settings.")

    settings = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found.")

    if request.share_financial_snapshots is not None:
        settings.share_financial_snapshots = request.share_financial_snapshots
    if request.announce_system_events is not None:
        settings.announce_system_events = request.announce_system_events
    if request.post_security_rule_updates is not None:
        settings.post_security_rule_updates = request.post_security_rule_updates
    if request.post_group_approval_polls is not None:
        settings.post_group_approval_polls = request.post_group_approval_polls
    if request.notify_important_rule_changes is not None:
        settings.notify_important_rule_changes = request.notify_important_rule_changes

    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Milestones and Security settings updated successfully."}
