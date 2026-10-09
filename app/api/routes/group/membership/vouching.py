from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select
import uuid
from typing import Optional, List

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.finance import GuarantorPledge
from app.models.group.settings import GroupGovernanceSettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership"])

class VouchRequest(BaseModel):
    borrower_user_id: uuid.UUID = Field(..., description="The user you are vouching for")
    maximum_liability_amount: float = Field(..., description="The maximum amount you are willing to cover if they default")

class ReviewVouchRequest(BaseModel):
    action: str = Field(..., description="'ACCEPT' or 'REJECT'")

@router.post("/{group_id}/vouch", summary="Vouch for a Member")
def submit_endorsement(
    group_id: str,
    request: VouchRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Submit an endorsement (Guarantor Pledge) for another member in the group.
    """
    if current_user.id == request.borrower_user_id:
        raise HTTPException(status_code=400, detail="You cannot vouch for yourself.")

    # 1. Verify both are members of the group
    guarantor_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    
    if not guarantor_membership:
        raise HTTPException(status_code=403, detail="You are not a member of this group.")
        
    borrower_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == request.borrower_user_id
        )
    ).first()
    
    if not borrower_membership:
        raise HTTPException(status_code=404, detail="The user you are vouching for is not in this group.")

    # 2. Check if a pledge already exists
    existing_pledge = session.exec(
        select(GuarantorPledge).where(
            GuarantorPledge.group_id == group_id,
            GuarantorPledge.guarantor_user_id == current_user.id,
            GuarantorPledge.borrower_user_id == request.borrower_user_id,
            GuarantorPledge.status == "ACTIVE"
        )
    ).first()
    
    if existing_pledge:
        raise HTTPException(status_code=400, detail="You are already actively vouching for this user.")

    # 3. Create the Pledge
    new_pledge = GuarantorPledge(
        group_id=group_id,
        guarantor_user_id=current_user.id,
        borrower_user_id=request.borrower_user_id,
        maximum_liability_amount=request.maximum_liability_amount,
        status="ACTIVE"
    )
    
    session.add(new_pledge)
    session.commit()
    session.refresh(new_pledge)
    
    return {
        "status": "success",
        "message": "You have successfully vouched for this member.",
        "data": new_pledge.dict()
    }

@router.get("/{group_id}/vouch/me", summary="Review Endorsements (My Pledges)")
def get_my_endorsements(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get all members you have vouched for, and all members who have vouched for you.
    """
    vouched_for_others = session.exec(
        select(GuarantorPledge).where(
            GuarantorPledge.group_id == group_id,
            GuarantorPledge.guarantor_user_id == current_user.id
        )
    ).all()
    
    vouched_by_others = session.exec(
        select(GuarantorPledge).where(
            GuarantorPledge.group_id == group_id,
            GuarantorPledge.borrower_user_id == current_user.id
        )
    ).all()
    
    return {
        "vouched_for_others": [p.dict() for p in vouched_for_others],
        "vouched_by_others": [p.dict() for p in vouched_by_others]
    }
