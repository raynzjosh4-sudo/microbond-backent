from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupVisibilitySettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdatePrivacySettingsRequest(BaseModel):
    hide_total_group_balance: Optional[bool] = None
    hide_member_contact_info: Optional[bool] = None
    invite_only_discoverability: Optional[bool] = None
    
    vis_member_total_savings: Optional[bool] = None
    
    vis_report_expected_revenue: Optional[bool] = None
    vis_report_actual_collection: Optional[bool] = None
    vis_report_deficit: Optional[bool] = None
    vis_report_reserve_fund: Optional[bool] = None
    vis_report_escrow_holds: Optional[bool] = None


@router.get("/{group_id}/settings/privacy", summary="Get Group Privacy Settings")
def get_group_privacy_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the Advanced Group Privacy settings for the group.
    Accessible by any active group member or admin.
    """
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
        raise HTTPException(status_code=403, detail="You must be a member of this group to view privacy settings.")

    vis_settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group.group_id)
    ).first()
    
    if not vis_settings:
        vis_settings = GroupVisibilitySettings(group_id=group.group_id)
        session.add(vis_settings)
        session.commit()
        session.refresh(vis_settings)

    return {
        "status": "success",
        "data": {
            "group_id": group.group_id,
            "group_name": group.name,
            "hide_total_group_balance": vis_settings.hide_total_group_balance,
            "hide_member_contact_info": vis_settings.hide_member_contact_info,
            "invite_only_discoverability": vis_settings.invite_only_discoverability,
            "deposit_widget_visibility": getattr(vis_settings, "deposit_widget_visibility", "ALL_MEMBERS"),
            "vis_member_total_savings": getattr(vis_settings, "vis_member_total_savings", True),
            "vis_report_expected_revenue": vis_settings.vis_report_expected_revenue,
            "vis_report_actual_collection": vis_settings.vis_report_actual_collection,
            "vis_report_deficit": vis_settings.vis_report_deficit,
            "vis_report_reserve_fund": vis_settings.vis_report_reserve_fund,
            "vis_report_escrow_holds": vis_settings.vis_report_escrow_holds,
        }
    }


@router.patch("/{group_id}/settings/privacy", summary="Update Group Privacy Settings")
def update_group_privacy_settings(
    group_id: str, 
    request: UpdatePrivacySettingsRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the Advanced Group Privacy settings. Only the Group Admin can perform this action.
    """
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
        raise HTTPException(status_code=403, detail="Only the Group Admin can update privacy settings.")

    vis_settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group.group_id)
    ).first()
    
    if not vis_settings:
        vis_settings = GroupVisibilitySettings(group_id=group.group_id)
        session.add(vis_settings)
        
    if request.hide_total_group_balance is not None:
        vis_settings.hide_total_group_balance = request.hide_total_group_balance
    if request.hide_member_contact_info is not None:
        vis_settings.hide_member_contact_info = request.hide_member_contact_info
    if request.invite_only_discoverability is not None:
        vis_settings.invite_only_discoverability = request.invite_only_discoverability
    if request.vis_member_total_savings is not None:
        vis_settings.vis_member_total_savings = request.vis_member_total_savings
        
    if request.vis_report_expected_revenue is not None:
        vis_settings.vis_report_expected_revenue = request.vis_report_expected_revenue
    if request.vis_report_actual_collection is not None:
        vis_settings.vis_report_actual_collection = request.vis_report_actual_collection
    if request.vis_report_deficit is not None:
        vis_settings.vis_report_deficit = request.vis_report_deficit
    if request.vis_report_reserve_fund is not None:
        vis_settings.vis_report_reserve_fund = request.vis_report_reserve_fund
    if request.vis_report_escrow_holds is not None:
        vis_settings.vis_report_escrow_holds = request.vis_report_escrow_holds

    session.add(vis_settings)
    session.commit()
    session.refresh(vis_settings)

    return {
        "status": "success",
        "message": "Privacy settings updated.",
        "data": {
            "group_id": group.group_id,
            "group_name": group.name,
            "hide_total_group_balance": vis_settings.hide_total_group_balance,
            "hide_member_contact_info": vis_settings.hide_member_contact_info,
            "invite_only_discoverability": vis_settings.invite_only_discoverability,
            "deposit_widget_visibility": getattr(vis_settings, "deposit_widget_visibility", "ALL_MEMBERS"),
            "vis_member_total_savings": getattr(vis_settings, "vis_member_total_savings", True),
            "vis_report_expected_revenue": vis_settings.vis_report_expected_revenue,
            "vis_report_actual_collection": vis_settings.vis_report_actual_collection,
            "vis_report_deficit": vis_settings.vis_report_deficit,
            "vis_report_reserve_fund": vis_settings.vis_report_reserve_fund,
            "vis_report_escrow_holds": vis_settings.vis_report_escrow_holds,
        }
    }
