from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupFinancialSettings, GroupVisibilitySettings

router = APIRouter(prefix="/api/v1/groups", tags=["Escrow Lock Settings"])


class UpdateEscrowLockRequest(BaseModel):
    # Hold funds in escrow: Contributions are temporarily locked in a smart escrow until release conditions are met
    enable_escrow: Optional[bool] = Field(default=None, description="Hold funds in escrow toggle")
    hold_funds_in_escrow: Optional[bool] = Field(default=None, description="Alias for enable_escrow")
    
    # Release condition: e.g. 'Upon unanimous approval', 'Majority Vote', 'Timelock Expiry'
    escrow_release_condition: Optional[str] = Field(default=None, description="Condition required to release funds from escrow")
    release_condition: Optional[str] = Field(default=None, description="Alias for escrow_release_condition")


@router.get("/{group_id}/settings/escrow", summary="Get Escrow Lock Settings")
def get_escrow_lock_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the Escrow Lock & Fund Protection configuration:
    1. Hold funds in escrow (enable_escrow)
    2. Release condition (escrow_release_condition)
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

    fin = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    if not fin:
        fin = GroupFinancialSettings(group_id=group_id)
        session.add(fin)
        session.commit()
        session.refresh(fin)

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "group_name": group.name,
            "enable_escrow": fin.enable_escrow,
            "hold_funds_in_escrow": fin.enable_escrow,
            "escrow_release_condition": fin.escrow_release_condition,
            "release_condition": fin.escrow_release_condition,
            "available_release_conditions": [
                "Upon unanimous approval",
                "Majority Vote",
                "Timelock or Consensus",
                "Milestone and Consensus"
            ]
        }
    }


@router.patch("/{group_id}/settings/escrow", summary="Update Escrow Lock Settings")
def update_escrow_lock_settings(
    group_id: str,
    request: UpdateEscrowLockRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates Escrow Lock settings. Only the Group Admin can update this configuration.
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
        raise HTTPException(status_code=403, detail="Only the Group Admin can update escrow settings.")

    fin = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id).with_for_update()
    ).first()
    if not fin:
        fin = GroupFinancialSettings(group_id=group_id)

    # Apply enable_escrow / hold_funds_in_escrow
    escrow_val = request.hold_funds_in_escrow if request.hold_funds_in_escrow is not None else request.enable_escrow
    if escrow_val is not None:
        fin.enable_escrow = escrow_val

    # Apply escrow_release_condition / release_condition
    condition_val = request.release_condition if request.release_condition is not None else request.escrow_release_condition
    if condition_val is not None:
        fin.escrow_release_condition = condition_val

    session.add(fin)
    session.commit()
    session.refresh(fin)

    return {
        "status": "success",
        "message": "Escrow lock settings updated successfully",
        "data": {
            "group_id": group_id,
            "group_name": group.name,
            "enable_escrow": fin.enable_escrow,
            "hold_funds_in_escrow": fin.enable_escrow,
            "escrow_release_condition": fin.escrow_release_condition,
            "release_condition": fin.escrow_release_condition
        }
    }
