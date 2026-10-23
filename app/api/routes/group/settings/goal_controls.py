from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.long_term import TargetSavingsGroupDetails
from app.models.group.settings import GroupVisibilitySettings

router = APIRouter(prefix="/api/v1/groups", tags=["Goal Controls Settings"])


class UpdateGoalControlsRequest(BaseModel):
    # Lock funds: Freeze contributions until the group goal is met
    lock_funds: Optional[bool] = Field(default=None, description="Freeze contributions until the group goal is met")
    is_locked: Optional[bool] = Field(default=None, description="Alias for lock_funds")
    
    # Hide leaderboard: Hide member-by-member savings totals
    hide_leaderboard: Optional[bool] = Field(default=None, description="Hide member-by-member savings totals")
    
    # Let members view their total saved: When off, members cannot see their personal savings total
    vis_member_total_savings: Optional[bool] = Field(default=None, description="Let members view their total saved")
    let_members_view_total_saved: Optional[bool] = Field(default=None, description="Alias for vis_member_total_savings")


@router.get("/{group_id}/settings/goal-controls", summary="Get Goal Controls Settings")
def get_goal_controls_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the 3 Goal Controls settings:
    1. Lock funds (freeze contributions until group goal is met)
    2. Hide leaderboard (hide member-by-member savings totals)
    3. Let members view their total saved (when off, members cannot see their personal savings total)
    """
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")

    # Target savings details
    details = session.exec(
        select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
    ).first()

    # Visibility settings
    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    if not vis:
        vis = GroupVisibilitySettings(group_id=group_id)
        session.add(vis)
        session.commit()
        session.refresh(vis)

    is_locked = details.is_locked if details else False
    hide_leaderboard = details.hide_leaderboard if details else False
    vis_member_total_savings = getattr(vis, "vis_member_total_savings", True)

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "group_name": group.name,
            "lock_funds": is_locked,
            "is_locked": is_locked,
            "hide_leaderboard": hide_leaderboard,
            "vis_member_total_savings": vis_member_total_savings,
            "let_members_view_total_saved": vis_member_total_savings,
        }
    }


@router.patch("/{group_id}/settings/goal-controls", summary="Update Goal Controls Settings")
def update_goal_controls_settings(
    group_id: str,
    request: UpdateGoalControlsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the Goal Controls toggles. Only the Group Admin can update these settings.
    """
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update goal controls.")

    # 1. Update TargetSavingsGroupDetails (lock_funds / is_locked, hide_leaderboard)
    details = session.exec(
        select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id).with_for_update()
    ).first()

    locked_val = request.lock_funds if request.lock_funds is not None else request.is_locked
    if details:
        if locked_val is not None:
            details.is_locked = locked_val
        if request.hide_leaderboard is not None:
            details.hide_leaderboard = request.hide_leaderboard
        session.add(details)

    # 2. Update GroupVisibilitySettings (vis_member_total_savings / let_members_view_total_saved)
    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id).with_for_update()
    ).first()
    if not vis:
        vis = GroupVisibilitySettings(group_id=group_id)

    vis_val = request.let_members_view_total_saved if request.let_members_view_total_saved is not None else request.vis_member_total_savings
    if vis_val is not None:
        vis.vis_member_total_savings = vis_val
        session.add(vis)

    session.commit()
    if details:
        session.refresh(details)
    session.refresh(vis)

    is_locked = details.is_locked if details else False
    hide_leaderboard = details.hide_leaderboard if details else False
    vis_member_total_savings = getattr(vis, "vis_member_total_savings", True)

    return {
        "status": "success",
        "message": "Goal controls updated successfully",
        "data": {
            "group_id": group_id,
            "group_name": group.name,
            "lock_funds": is_locked,
            "is_locked": is_locked,
            "hide_leaderboard": hide_leaderboard,
            "vis_member_total_savings": vis_member_total_savings,
            "let_members_view_total_saved": vis_member_total_savings,
        }
    }
