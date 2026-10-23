from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupGovernanceSettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdatePermissionsSettingsRequest(BaseModel):
    members_can_edit_settings: Optional[bool] = None
    members_can_send_messages: Optional[bool] = None
    members_can_invite_via_link: Optional[bool] = None
    members_can_manage_payout_roster: Optional[bool] = None
    
    # Admin Permissions
    admins_must_approve_new_members: Optional[bool] = None

@router.get("/{group_id}/settings/permissions", summary="Get Group Permissions Settings")
def get_group_permissions_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")
        
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be a member to view group permissions.")
        
    gov_settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group.group_id)
    ).first()
    if not gov_settings:
        raise HTTPException(status_code=404, detail="Governance settings not found.")
        
    return {
        "status": "success",
        "data": {
            "members_can_edit_settings": gov_settings.members_can_edit_settings,
            "members_can_send_messages": gov_settings.members_can_send_messages,
            "members_can_invite_via_link": gov_settings.members_can_invite_via_link,
            "members_can_manage_payout_roster": gov_settings.members_can_manage_payout_roster,
            "admins_must_approve_new_members": bool(gov_settings.admins_must_approve_new_members or gov_settings.requires_admin_approval),
            "allow_turn_swaps": gov_settings.allow_turn_swaps
        }
    }

@router.patch("/{group_id}/settings/permissions", summary="Update Group Permissions Settings")
def update_group_permissions_settings(
    group_id: str, 
    request: UpdatePermissionsSettingsRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")
        
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()
    
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update permissions settings.")

    gov_settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group.group_id)
    ).first()
    if not gov_settings:
        raise HTTPException(status_code=404, detail="Governance settings not found.")
        
    if request.members_can_edit_settings is not None:
        gov_settings.members_can_edit_settings = request.members_can_edit_settings
    if request.members_can_send_messages is not None:
        gov_settings.members_can_send_messages = request.members_can_send_messages
    if request.members_can_invite_via_link is not None:
        gov_settings.members_can_invite_via_link = request.members_can_invite_via_link
    if request.members_can_manage_payout_roster is not None:
        gov_settings.members_can_manage_payout_roster = request.members_can_manage_payout_roster
    if request.admins_must_approve_new_members is not None:
        gov_settings.admins_must_approve_new_members = request.admins_must_approve_new_members
        gov_settings.requires_admin_approval = request.admins_must_approve_new_members

    session.commit()
    session.refresh(gov_settings)
    return {
        "status": "success",
        "message": "Permissions settings updated.",
        "data": {
            "members_can_edit_settings": gov_settings.members_can_edit_settings,
            "members_can_send_messages": gov_settings.members_can_send_messages,
            "members_can_invite_via_link": gov_settings.members_can_invite_via_link,
            "members_can_manage_payout_roster": gov_settings.members_can_manage_payout_roster,
            "admins_must_approve_new_members": bool(gov_settings.admins_must_approve_new_members or gov_settings.requires_admin_approval),
            "allow_turn_swaps": gov_settings.allow_turn_swaps
        }
    }
