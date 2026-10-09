from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupFinancialSettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateGeneralSettingsRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    maximum_member_capacity: Optional[int] = None
    late_fee_amount: Optional[float] = None
    reserve_fund_percentage: Optional[float] = None
    
@router.put("/{group_id}/settings/general", summary="Update Group Settings")
def update_group_settings(
    group_id: str, 
    request: UpdateGeneralSettingsRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    group = session.query(Group).filter(Group.group_id == group_id).with_for_update().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")
        
    admin_membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group.group_id,
        GroupMembership.user_id == current_user.id,
        GroupMembership.role == "ADMIN"
    ).first()
    
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update settings.")

    # Apply Base Group Updates
    if request.name is not None:
        group.name = request.name
    if request.description is not None:
        group.description = request.description
    if request.maximum_member_capacity is not None:
        current_members = session.query(GroupMembership).filter(GroupMembership.group_id == group_id).count()
        if request.maximum_member_capacity < current_members:
            raise HTTPException(status_code=400, detail="Cannot lower capacity below the current number of joined members.")
        group.max_members = request.maximum_member_capacity

    # Apply Financial Settings
    settings = session.query(GroupFinancialSettings).filter(GroupFinancialSettings.group_id == group.group_id).first()
    if request.late_fee_amount is not None:
        settings.late_fee_amount = request.late_fee_amount
    if request.reserve_fund_percentage is not None:
        settings.reserve_fund_percentage = request.reserve_fund_percentage

    session.commit()
    return {"status": "success", "message": "General settings updated."}
