from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupGovernanceSettings
from app.models.group.rotating import RotatingGroupDetails
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdatePermissionsSettingsRequest(BaseModel):
    members_can_edit_settings: Optional[bool] = None
    members_can_send_messages: Optional[bool] = None
    members_can_invite_via_link: Optional[bool] = None
    members_can_manage_payout_roster: Optional[bool] = None
    
    # Admin Permissions (requires_admin_approval is authoritative)
    admins_must_approve_new_members: Optional[bool] = None
    requires_admin_approval: Optional[bool] = None
    allow_turn_swaps: Optional[bool] = None

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

    rotating_details = session.exec(
        select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group.group_id)
    ).first()
    allow_turn_swaps = rotating_details.allow_turn_swaps if rotating_details else False
        
    return {
        "status": "success",
        "data": {
            "members_can_edit_settings": gov_settings.members_can_edit_settings,
            "members_can_send_messages": gov_settings.members_can_send_messages,
            "members_can_invite_via_link": gov_settings.members_can_invite_via_link,
            "members_can_manage_payout_roster": gov_settings.members_can_manage_payout_roster,
            "admins_must_approve_new_members": gov_settings.requires_admin_approval,
            "requires_admin_approval": gov_settings.requires_admin_approval,
            "allow_turn_swaps": allow_turn_swaps
        }
    }

@router.patch("/{group_id}/settings/permissions", summary="Update Group Permissions Settings")
def update_group_permissions_settings(
    group_id: str, 
    request: UpdatePermissionsSettingsRequest, 
    background_tasks: BackgroundTasks = BackgroundTasks(),
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

    rotating_details = session.exec(
        select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group.group_id)
    ).first()

    admin_name = current_user.full_name or "Admin"
    change_notices = []

    if request.members_can_edit_settings is not None and request.members_can_edit_settings != gov_settings.members_can_edit_settings:
        gov_settings.members_can_edit_settings = request.members_can_edit_settings
        if request.members_can_edit_settings:
            change_notices.append("Edit Group Settings: Allowed for all members. Members can now modify group profile information and preferences.")
        else:
            change_notices.append("Edit Group Settings: Admin only. Only administrators can now change group profile details and configurations.")

    if request.members_can_send_messages is not None and request.members_can_send_messages != gov_settings.members_can_send_messages:
        gov_settings.members_can_send_messages = request.members_can_send_messages
        if request.members_can_send_messages:
            change_notices.append("Send Messages: Allowed for all members. All active members can now post messages in the group chat.")
        else:
            change_notices.append("Send Messages: Admin only. The chat is now read-only for regular members; only group admins can post messages.")

    if request.members_can_invite_via_link is not None and request.members_can_invite_via_link != gov_settings.members_can_invite_via_link:
        gov_settings.members_can_invite_via_link = request.members_can_invite_via_link
        if request.members_can_invite_via_link:
            change_notices.append("Invite via Link: Allowed for all members. Any active member can now share the group invite link to bring in new members.")
        else:
            change_notices.append("Invite via Link: Admin only. Only administrators can now generate or share group invite links.")

    if request.members_can_manage_payout_roster is not None and request.members_can_manage_payout_roster != gov_settings.members_can_manage_payout_roster:
        gov_settings.members_can_manage_payout_roster = request.members_can_manage_payout_roster
        if request.members_can_manage_payout_roster:
            change_notices.append("Manage Payout Roster: Allowed for members. Members can now help arrange the payout order.")
        else:
            change_notices.append("Manage Payout Roster: Admin only. Only administrators can manage and adjust the payout order.")

    admin_approval_target = request.requires_admin_approval if request.requires_admin_approval is not None else request.admins_must_approve_new_members
    if admin_approval_target is not None and admin_approval_target != gov_settings.requires_admin_approval:
        gov_settings.requires_admin_approval = admin_approval_target
        if admin_approval_target:
            change_notices.append("Approve New Members: Enabled. Anyone joining via invite link must be approved by an administrator before gaining access.")
        else:
            change_notices.append("Approve New Members: Disabled. New members joining via invite link will automatically enter without waiting for approval.")

    if request.allow_turn_swaps is not None and rotating_details and request.allow_turn_swaps != rotating_details.allow_turn_swaps:
        rotating_details.allow_turn_swaps = request.allow_turn_swaps
        session.add(rotating_details)
        if request.allow_turn_swaps:
            change_notices.append("Turn Swaps: Enabled. Members can now request to swap payout turns with each other.")
        else:
            change_notices.append("Turn Swaps: Disabled. Payout turn order is now fixed and cannot be swapped.")

    session.add(gov_settings)
    session.commit()
    session.refresh(gov_settings)

    if change_notices:
        bullet_points = "\n".join(f"• {c}" for c in change_notices)
        system_text = f"🔒 Group Permissions Updated by {admin_name}:\n{bullet_points}"
        system_msg = broadcast_system_message_sync(
            group_id=group_id,
            message_text=system_text,
            message_type="SYSTEM_EVENT",
            sender_id="SYSTEM",
            session=session,
            background_tasks=background_tasks,
            attachments=[{
                "category": "SETTINGS_UPDATE",
                "setting_type": "PERMISSIONS",
                "admin_id": str(current_user.id),
                "admin_name": admin_name,
                "changes_count": len(change_notices)
            }]
        )
        if background_tasks is None and system_msg:
            try:
                import asyncio
                asyncio.create_task(
                    ws_manager.broadcast_to_group(
                        group_id,
                        {
                            "event_type": "NEW_MESSAGE",
                            "message": system_msg.model_dump(mode="json")
                        }
                    )
                )
            except Exception:
                pass

    allow_turn_swaps = rotating_details.allow_turn_swaps if rotating_details else False

    return {
        "status": "success",
        "message": "Permissions settings updated.",
        "data": {
            "members_can_edit_settings": gov_settings.members_can_edit_settings,
            "members_can_send_messages": gov_settings.members_can_send_messages,
            "members_can_invite_via_link": gov_settings.members_can_invite_via_link,
            "members_can_manage_payout_roster": gov_settings.members_can_manage_payout_roster,
            "admins_must_approve_new_members": gov_settings.requires_admin_approval,
            "requires_admin_approval": gov_settings.requires_admin_approval,
            "allow_turn_swaps": allow_turn_swaps
        }
    }
