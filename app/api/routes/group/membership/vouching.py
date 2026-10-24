import json
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlmodel import Session, select
import uuid
from typing import Optional, List, Dict, Any

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.finance import GuarantorPledge, MemberObligation
from app.models.group.settings import GroupGovernanceSettings
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.core.microbond_core import detect_guarantor_cycle, evaluate_guarantor_capacity

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership"])


class VouchRequest(BaseModel):
    borrower_user_id: uuid.UUID = Field(..., description="The user you are vouching for")
    maximum_liability_amount: float = Field(..., description="The maximum amount in UGX you are willing to cover if they default")


class ReviewVouchRequest(BaseModel):
    action: str = Field(..., description="'ACCEPT' or 'REJECT'")


@router.post("/{group_id}/vouch", summary="Vouch for a Member")
def submit_endorsement(
    group_id: str,
    request: VouchRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Submit an endorsement (Guarantor Pledge) for another member in the group.
    Evaluates anti-collusion cyclic traps and guarantor capacity using the Rust microbond_core engine.
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

    # 3. Rust Engine Anti-Collusion DAG Verification
    all_active_pledges = session.exec(
        select(GuarantorPledge).where(
            GuarantorPledge.group_id == group_id,
            GuarantorPledge.status == "ACTIVE"
        )
    ).all()
    edges = [(str(p.guarantor_user_id), str(p.borrower_user_id)) for p in all_active_pledges]

    if detect_guarantor_cycle(edges, str(current_user.id), str(request.borrower_user_id)):
        raise HTTPException(
            status_code=400,
            detail="Cyclic vouching detected: You cannot vouch for someone who is already in your guarantee chain."
        )

    # 4. Rust Engine Guarantor Risk Capacity Evaluation
    bad_obligations = session.exec(
        select(MemberObligation).where(
            MemberObligation.user_id == current_user.id,
            MemberObligation.status.in_(["LATE", "DEFAULTED"])
        )
    ).all()
    bad_count = len(bad_obligations)

    current_active_liability = sum(
        p.maximum_liability_amount for p in all_active_pledges if p.guarantor_user_id == current_user.id
    )

    capacity_raw = evaluate_guarantor_capacity(
        guarantor_trust_score=guarantor_membership.group_trust_score or 100,
        total_contributed_minor=guarantor_membership.total_contributed or 0,
        current_active_liability_minor=int(current_active_liability),
        new_pledge_minor=int(request.maximum_liability_amount),
        bad_obligations_count=bad_count,
        min_guarantor_trust_score=70,
        base_allowance_minor=1_000_000,
    )
    capacity_res = json.loads(capacity_raw)
    if not capacity_res.get("is_approved", True):
        raise HTTPException(
            status_code=400,
            detail=capacity_res.get("rejection_reason", "Guarantor capacity limit exceeded.")
        )

    # 5. Create the Pledge
    new_pledge = GuarantorPledge(
        group_id=group_id,
        guarantor_user_id=current_user.id,
        borrower_user_id=request.borrower_user_id,
        maximum_liability_amount=int(request.maximum_liability_amount),
        status="ACTIVE"
    )
    
    session.add(new_pledge)
    session.commit()
    session.refresh(new_pledge)
    
    # --- CHAT & AUDIT INTEGRATION ---
    borrower = session.get(User, request.borrower_user_id)
    borrower_name = borrower.full_name if borrower else "a member"
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"{current_user.full_name} vouched for {borrower_name} up to {int(request.maximum_liability_amount):,} UGX.",
        message_type="TRUST_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )
    
    return {
        "status": "success",
        "message": f"You have successfully vouched for {borrower_name}.",
        "data": {
            "pledge_id": new_pledge.id,
            "pledge_token": new_pledge.pledge_token,
            "borrower_user_id": str(new_pledge.borrower_user_id),
            "borrower_name": borrower_name,
            "maximum_liability_amount": new_pledge.maximum_liability_amount,
            "maximum_liability_formatted": f"{int(new_pledge.maximum_liability_amount):,} UGX",
            "status": new_pledge.status
        }
    }


@router.get("/{group_id}/vouch/me", summary="Review Endorsements (My Pledges)")
def get_my_endorsements(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get all members you have vouched for, and all members who have vouched for you,
    with full profile details and formatted amounts.
    """
    vouched_for_others = session.exec(
        select(GuarantorPledge, User)
        .join(User, GuarantorPledge.borrower_user_id == User.id)
        .where(
            GuarantorPledge.group_id == group_id,
            GuarantorPledge.guarantor_user_id == current_user.id
        )
    ).all()
    
    vouched_by_others = session.exec(
        select(GuarantorPledge, User)
        .join(User, GuarantorPledge.guarantor_user_id == User.id)
        .where(
            GuarantorPledge.group_id == group_id,
            GuarantorPledge.borrower_user_id == current_user.id
        )
    ).all()
    
    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "user_id": str(current_user.id),
            "vouched_for_others": [
                {
                    "pledge_id": p.id,
                    "pledge_token": p.pledge_token,
                    "borrower_user_id": str(u.id),
                    "borrower_name": u.full_name or "Member",
                    "borrower_phone": u.phone_number,
                    "borrower_avatar": getattr(u, "profile_picture_url", None),
                    "maximum_liability_amount": p.maximum_liability_amount,
                    "maximum_liability_formatted": f"{int(p.maximum_liability_amount):,} UGX",
                    "status": p.status,
                    "created_at": p.created_at
                }
                for p, u in vouched_for_others
            ],
            "vouched_by_others": [
                {
                    "pledge_id": p.id,
                    "pledge_token": p.pledge_token,
                    "guarantor_user_id": str(u.id),
                    "guarantor_name": u.full_name or "Guarantor",
                    "guarantor_phone": u.phone_number,
                    "guarantor_avatar": getattr(u, "profile_picture_url", None),
                    "maximum_liability_amount": p.maximum_liability_amount,
                    "maximum_liability_formatted": f"{int(p.maximum_liability_amount):,} UGX",
                    "status": p.status,
                    "created_at": p.created_at
                }
                for p, u in vouched_by_others
            ]
        }
    }

