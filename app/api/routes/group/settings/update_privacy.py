from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
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
    
    vis_report_expected_revenue: Optional[bool] = None
    vis_report_actual_collection: Optional[bool] = None
    vis_report_deficit: Optional[bool] = None
    vis_report_reserve_fund: Optional[bool] = None
    vis_report_escrow_holds: Optional[bool] = None
    
@router.put("/{group_id}/settings/privacy", summary="Update Group Privacy Settings")
def update_group_privacy_settings(
    group_id: str, 
    request: UpdatePrivacySettingsRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    group = session.query(Group).filter(Group.group_id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")
        
    admin_membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group.group_id,
        GroupMembership.user_id == current_user.id,
        GroupMembership.role == "ADMIN"
    ).first()
    
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update privacy settings.")

    vis_settings = session.query(GroupVisibilitySettings).filter(GroupVisibilitySettings.group_id == group.group_id).first()
    if not vis_settings:
        raise HTTPException(status_code=404, detail="Visibility settings not found.")
        
    if request.hide_total_group_balance is not None:
        vis_settings.hide_total_group_balance = request.hide_total_group_balance
    if request.hide_member_contact_info is not None:
        vis_settings.hide_member_contact_info = request.hide_member_contact_info
    if request.invite_only_discoverability is not None:
        vis_settings.invite_only_discoverability = request.invite_only_discoverability
        
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
    return {"status": "success", "message": "Privacy settings updated."}
