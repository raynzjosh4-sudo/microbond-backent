from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import GroupMembership
from app.models.user.user import User
from app.models.group.long_term import TargetSavingsGroupDetails
from app.models.group.settings import GroupVisibilitySettings

router = APIRouter()

@router.get("/{group_id}/settings", summary="Get Target Savings Group Settings")
def get_target_savings_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the target savings rules, current saved totals, and consensus settings for active members.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")

    details = session.exec(
        select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
    ).first()
    if not details:
        raise HTTPException(status_code=404, detail="Target savings details not found for this group.")

    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()

    data = details.model_dump(mode="json")
    data["lock_funds"] = details.is_locked
    data["vis_member_total_savings"] = getattr(vis, "vis_member_total_savings", True) if vis else True
    data["let_members_view_total_saved"] = data["vis_member_total_savings"]

    return {
        "status": "success",
        "data": data
    }
