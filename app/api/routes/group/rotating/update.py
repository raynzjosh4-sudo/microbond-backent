from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from sqlalchemy import cast, String
from typing import Optional
from pydantic import BaseModel
import datetime

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.rotating import RotatingGroupDetails

router = APIRouter()

class UpdateRotatingSettingsRequest(BaseModel):
    # Logistics
    contribution_amount: Optional[float] = None
    group_start_time: Optional[int] = None
    payout_order_strategy: Optional[str] = None
    require_guarantor: Optional[bool] = None

@router.put("/{group_id}/settings/rotating", summary="Update Rotating Group Settings")
@router.patch("/{group_id}/settings/rotating", summary="Partial Update Rotating Group Settings")
def update_rotating_group_settings(
    group_id: str,
    request: UpdateRotatingSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    group = session.query(Group).filter(Group.group_id == group_id).with_for_update().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")
        
    admin_membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group.group_id,
        cast(GroupMembership.user_id, String) == str(current_user.id),
        GroupMembership.role == "ADMIN",
        GroupMembership.status == "ACTIVE"
    ).first()
    
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update settings.")

    details = session.query(RotatingGroupDetails).filter(RotatingGroupDetails.group_id == group.group_id).first()
    
    if group.status == "ACTIVE" or details.is_payout_order_locked:
        raise HTTPException(
            status_code=400, 
            detail="Settings are permanently locked. You cannot modify rotating logistics after the cycle has launched."
        )

    if request.contribution_amount is not None:
        details.contribution_amount = request.contribution_amount
        if group.max_members:
            details.total_expected_pool_per_cycle = request.contribution_amount * group.max_members
            
    if request.group_start_time is not None:
        current_time = int(datetime.datetime.utcnow().timestamp())
        if request.group_start_time <= current_time:
            raise HTTPException(status_code=400, detail="New start time must be in the future.")
        details.group_start_time = request.group_start_time
        
    if request.payout_order_strategy is not None:
        details.payout_order_strategy = request.payout_order_strategy
        
    if request.require_guarantor is not None:
        details.require_guarantor = request.require_guarantor

    session.commit()
    return {"status": "success", "message": "Rotating specific settings updated successfully."}
