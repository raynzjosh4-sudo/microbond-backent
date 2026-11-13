from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select
from pydantic import BaseModel, Field
import urllib.parse

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group
from app.models.group.core.membership_join_request import MembershipJoinRequest
from app.models.group.finance import GuarantorPledge
from app.models.user.user import User
from app.core.token_security import generate_opaque_token, hash_opaque_token
from app.services.group.join_requests import maybe_activate_join_request
from app.services.audit_service import AuditService

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
    pledge = session.exec(
        select(GuarantorPledge)
        .where(
            GuarantorPledge.id == pledge_id,
            GuarantorPledge.borrower_user_id == current_user.id,
            GuarantorPledge.status == "PENDING_CONSENT",
        )
        .with_for_update()
    ).first()
    
    if not pledge:
        raise HTTPException(status_code=404, detail="Guarantor pledge not found or unauthorized.")

    group = session.exec(
        select(Group).where(Group.group_id == pledge.group_id)
    ).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found.")

    # Keep only a hash in storage; the bearer token is returned once in the link.
    token = generate_opaque_token()
    pledge.pledge_token_hash = hash_opaque_token(token)
    session.add(pledge)
    session.commit()
    deep_link = f"microbond://vouch?token={token}"
    
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
    pledge_token: str = Field(min_length=32, max_length=256)

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
    pledge = session.exec(
        select(GuarantorPledge)
        .where(GuarantorPledge.pledge_token_hash == hash_opaque_token(request.pledge_token))
        .with_for_update()
    ).first()
    
    if not pledge:
        raise HTTPException(status_code=404, detail="Invalid or expired pledge token.")
        
    if pledge.status != "PENDING_CONSENT":
        raise HTTPException(status_code=400, detail="This pledge has already been processed.")
        
    if pledge.guarantor_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the designated guarantor for this pledge.")
        
    join_request = session.exec(
        select(MembershipJoinRequest)
        .where(
            MembershipJoinRequest.group_id == pledge.group_id,
            MembershipJoinRequest.user_id == pledge.borrower_user_id,
            MembershipJoinRequest.public_status.notin_(
                ["APPROVED", "REJECTED", "CANCELLED", "EXPIRED"]
            ),
        )
        .with_for_update()
    ).first()
    if join_request is None or not join_request.requires_guarantor:
        raise HTTPException(status_code=409, detail="The related join request is no longer pending.")

    # 2. Check Guarantor's capacity
    locked_user = session.exec(
        select(User).where(User.id == current_user.id).with_for_update()
    ).first()
    if locked_user is None:
        raise HTTPException(status_code=404, detail="Guarantor account not found.")

    # If the Guarantor is already guaranteeing too many people, reject it.
    total_liability = session.exec(
        select(func.sum(GuarantorPledge.maximum_liability_amount)).where(
            GuarantorPledge.guarantor_user_id == current_user.id,
            GuarantorPledge.status == "ACTIVE",
        )
    ).one() or 0
    
    # Hard limit of 2,000,000 UGX total exposure across the platform
    if (total_liability + pledge.maximum_liability_amount) > 2000000:
        raise HTTPException(status_code=400, detail=f"Accepting this pledge exceeds your maximum legal exposure limit of 2,000,000 UGX. Current exposure: {total_liability}")

    # 3. Accept the Pledge
    pledge.status = "ACTIVE"
    session.add(pledge)
    activated = maybe_activate_join_request(
        session,
        join_request,
        current_user.id,
    )
    AuditService.record_event(
        session=session,
        action="GUARANTOR_PLEDGE_ACCEPTED",
        entity_type="membership_join_request",
        entity_id=str(join_request.id),
        payload={"pledge_id": pledge.id, "activated": activated},
        actor_user_id=current_user.id,
        tenant_group_id=pledge.group_id,
    )
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "status": "success",
        "message": (
            "You have vouched for this user. Their membership is now active."
            if activated
            else "You have vouched for this user. Their request is awaiting remaining approvals."
        ),
        "membership_status": join_request.public_status,
    }


@router.post("/{pledge_id}/decline")
def decline_guarantor_pledge(
    pledge_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    pledge = session.exec(
        select(GuarantorPledge)
        .where(
            GuarantorPledge.id == pledge_id,
            GuarantorPledge.guarantor_user_id == current_user.id,
            GuarantorPledge.status == "PENDING_CONSENT",
        )
        .with_for_update()
    ).first()
    if pledge is None:
        raise HTTPException(status_code=404, detail="Pending guarantor pledge not found.")

    join_request = session.exec(
        select(MembershipJoinRequest)
        .where(
            MembershipJoinRequest.group_id == pledge.group_id,
            MembershipJoinRequest.user_id == pledge.borrower_user_id,
            MembershipJoinRequest.public_status.notin_(
                ["APPROVED", "REJECTED", "CANCELLED", "EXPIRED"]
            ),
        )
        .with_for_update()
    ).first()
    if join_request is None:
        raise HTTPException(status_code=409, detail="The related join request is no longer pending.")

    now = datetime.now(timezone.utc)
    pledge.status = "REJECTED"
    join_request.public_status = "REJECTED"
    join_request.guarantor_status = "REJECTED"
    join_request.rejection_reason = "A required guarantor declined the request."
    join_request.rejected_at = now
    join_request.updated_at = now
    session.add_all([pledge, join_request])
    AuditService.record_event(
        session=session,
        action="GUARANTOR_PLEDGE_DECLINED",
        entity_type="membership_join_request",
        entity_id=str(join_request.id),
        payload={"pledge_id": pledge.id},
        actor_user_id=current_user.id,
        tenant_group_id=pledge.group_id,
    )
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "status": "success",
        "message": "The guarantor request was declined.",
        "membership_status": join_request.public_status,
    }
