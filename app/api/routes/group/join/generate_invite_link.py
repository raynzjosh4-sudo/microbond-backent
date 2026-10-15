from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import Optional
from pydantic import BaseModel
import urllib.parse

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import GuarantorPledge

router = APIRouter(prefix="/api/v1/groups/join/guarantor", tags=["Guarantor Invites"])

@router.get("/{pledge_id}/invite-link")
def generate_invite_link(
    pledge_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Generates a pre-filled message containing the cryptographic deep link for the Guarantor.
    """
    pledge = session.query(GuarantorPledge).filter(
        GuarantorPledge.id == pledge_id,
        GuarantorPledge.borrower_user_id == current_user.id
    ).first()
    
    if not pledge:
        raise HTTPException(status_code=404, detail="Guarantor pledge not found or unauthorized.")
        
    group = session.query(Group).filter(Group.group_id == pledge.group_id).first()
    
    # Create the cryptographic deep link (intercepted by the Android app)
    deep_link = f"microbond://vouch?token={pledge.pledge_token}"
    
    # Create the human-readable message
    message = f"Hey, I am joining a savings group on Microbond ({group.name}). The system requires 1 person to vouch for my reliability. Please click this link to guarantee my membership: {deep_link}"
    
    # URL Encode the message for generic sharing (WhatsApp, X, SMS, etc)
    encoded_message = urllib.parse.quote(message)
    
    return {
        "status": "success",
        "deep_link": deep_link,
        "message_plain": message,
        "message_encoded": encoded_message
    }

class AcceptPledgeRequest(BaseModel):
    pledge_token: str

@router.post("/accept")
def accept_guarantor_pledge(
    request: AcceptPledgeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    The endpoint the Guarantor calls (via the deep link) to legally accept liability.
    """
    # 1. Fetch the Pledge
    pledge = session.query(GuarantorPledge).filter(
        GuarantorPledge.pledge_token == request.pledge_token
    ).with_for_update().first()
    
    if not pledge:
        raise HTTPException(status_code=404, detail="Invalid or expired pledge token.")
        
    if pledge.status != "PENDING_CONSENT":
        raise HTTPException(status_code=400, detail="This pledge has already been processed.")
        
    if pledge.guarantor_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the designated guarantor for this pledge.")
        
    # 2. Check Guarantor's capacity
    # If the Guarantor is already guaranteeing too many people, reject it.
    from sqlalchemy import func
    total_liability = session.query(func.sum(GuarantorPledge.maximum_liability_amount)).filter(
        GuarantorPledge.guarantor_user_id == current_user.id,
        GuarantorPledge.status == "ACTIVE"
    ).scalar() or 0.0
    
    # Hard limit of 2,000,000 UGX total exposure across the platform
    if (total_liability + pledge.maximum_liability_amount) > 2000000:
        raise HTTPException(status_code=400, detail=f"Accepting this pledge exceeds your maximum legal exposure limit of 2,000,000 UGX. Current exposure: {total_liability}")

    # 3. Accept the Pledge
    pledge.status = "ACTIVE"
    
    # 4. Upgrade the Borrower's Membership Status
    borrower_membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == pledge.group_id,
        GroupMembership.user_id == pledge.borrower_user_id
    ).with_for_update().first()
    
    if borrower_membership and borrower_membership.status == "PENDING_GUARANTOR":
        borrower_membership.status = "ACTIVE"
        
        # Increase group member count
        group = session.query(Group).filter(Group.group_id == pledge.group_id).first()
        if group:
            group.member_count += 1
            
    session.commit()
    
    return {
        "status": "success",
        "message": "You have successfully vouched for this user. They are now an active member of the group."
    }

