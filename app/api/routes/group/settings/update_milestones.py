from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupCommunicationSettings, GroupVisibilitySettings
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])


class UpdateMilestoneSettingsRequest(BaseModel):
    share_financial_snapshots: Optional[bool] = None
    announce_system_events: Optional[bool] = None
    post_security_rule_updates: Optional[bool] = None
    post_group_approval_polls: Optional[bool] = None
    post_loan_approval_polls: Optional[bool] = None
    notify_important_rule_changes: Optional[bool] = None


@router.get("/{group_id}/settings/milestones", summary="Get Milestones & Security Settings")
def get_milestone_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the current Goal Milestones & Security event notification toggles
    and member visibility statuses.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this group.")

    is_admin = (membership.role == "ADMIN")

    comm = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()
    if not comm:
        comm = GroupCommunicationSettings(group_id=group_id)
        session.add(comm)
        session.commit()
        session.refresh(comm)

    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()

    response_data = {
        "group_id": group_id,
        "is_admin": is_admin,
        "share_financial_snapshots": comm.share_financial_snapshots,
        "announce_system_events": comm.announce_system_events,
        "post_security_rule_updates": comm.post_security_rule_updates,
        "post_group_approval_polls": comm.post_group_approval_polls,
        "post_loan_approval_polls": comm.post_loan_approval_polls,
        "notify_important_rule_changes": comm.notify_important_rule_changes
    }

    if is_admin:
        response_data["visibility_status"] = {
            "vis_share_financial_snapshots": vis.vis_share_financial_snapshots if vis else True,
            "vis_announce_system_events": vis.vis_announce_system_events if vis else True,
            "vis_post_security_rule_updates": vis.vis_post_security_rule_updates if vis else True,
            "vis_post_group_approval_polls": vis.vis_post_group_approval_polls if vis else True,
            "vis_post_loan_approval_polls": vis.vis_post_loan_approval_polls if vis else True,
            "vis_notify_important_rule_changes": vis.vis_notify_important_rule_changes if vis else True
        }
    else:
        # Filter hidden fields if regular member
        if vis and not vis.vis_share_financial_snapshots:
            response_data.pop("share_financial_snapshots", None)
        if vis and not vis.vis_announce_system_events:
            response_data.pop("announce_system_events", None)
        if vis and not vis.vis_post_security_rule_updates:
            response_data.pop("post_security_rule_updates", None)
        if vis and not vis.vis_post_group_approval_polls:
            response_data.pop("post_group_approval_polls", None)
        if vis and not vis.vis_post_loan_approval_polls:
            response_data.pop("post_loan_approval_polls", None)
        if vis and not vis.vis_notify_important_rule_changes:
            response_data.pop("notify_important_rule_changes", None)

    return {"status": "success", "data": response_data}


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
        settings = GroupCommunicationSettings(group_id=group_id)
        session.add(settings)

    if request.share_financial_snapshots is not None:
        settings.share_financial_snapshots = request.share_financial_snapshots
    if request.announce_system_events is not None:
        settings.announce_system_events = request.announce_system_events
    if request.post_security_rule_updates is not None:
        settings.post_security_rule_updates = request.post_security_rule_updates
    if request.post_group_approval_polls is not None:
        settings.post_group_approval_polls = request.post_group_approval_polls
    if request.post_loan_approval_polls is not None:
        settings.post_loan_approval_polls = request.post_loan_approval_polls
    if request.notify_important_rule_changes is not None:
        settings.notify_important_rule_changes = request.notify_important_rule_changes

    session.add(settings)

    AuditService.record_event(
        session=session,
        action="MILESTONES_SETTINGS_UPDATED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={
            "updated_by": str(current_user.id),
            "share_financial_snapshots": settings.share_financial_snapshots,
            "announce_system_events": settings.announce_system_events,
            "post_security_rule_updates": settings.post_security_rule_updates,
            "post_group_approval_polls": settings.post_group_approval_polls,
            "post_loan_approval_polls": settings.post_loan_approval_polls,
            "notify_important_rule_changes": settings.notify_important_rule_changes
        },
        actor_user_id=current_user.id
    )

    session.commit()
    session.refresh(settings)

    return {
        "status": "success",
        "message": "Milestones and Security settings updated successfully.",
        "data": {
            "share_financial_snapshots": settings.share_financial_snapshots,
            "announce_system_events": settings.announce_system_events,
            "post_security_rule_updates": settings.post_security_rule_updates,
            "post_group_approval_polls": settings.post_group_approval_polls,
            "post_loan_approval_polls": settings.post_loan_approval_polls,
            "notify_important_rule_changes": settings.notify_important_rule_changes
        }
    }
