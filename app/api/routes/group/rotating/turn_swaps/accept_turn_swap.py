import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.finance import TurnSwapRequest, GroupPayout, MemberObligation, utc_now
from app.models.group.settings import GroupGovernanceSettings
from app.models.group.rotating import RotatingGroupDetails
from app.core.firebase_config import send_push_notification
from app.core.microbond_core import validate_turn_swap_eligibility

router = APIRouter()

@router.post("/{group_id}/swaps/{swap_request_id}/accept", summary="Accept a turn swap request")
def accept_turn_swap(
    group_id: str,
    swap_request_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    is_numeric = str(swap_request_id).isdigit()
    swap = session.query(TurnSwapRequest).filter(
        TurnSwapRequest.group_id == group_id,
        (TurnSwapRequest.swap_request_id == swap_request_id) | (TurnSwapRequest.id == (int(swap_request_id) if is_numeric else -1))
    ).first()
    
    if not swap:
        raise HTTPException(status_code=404, detail="Swap request not found.")
        
    if swap.target_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the targeted user can accept this swap.")
        
    if swap.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Cannot accept a swap that is {swap.status}.")

    # 1. Fetch the exact payouts
    requester_payout = session.query(GroupPayout).filter_by(
        group_id=group_id,
        user_id=swap.requester_user_id,
        cycle_number=swap.requester_cycle_number,
        status="PENDING"
    ).first()
    
    target_payout = session.query(GroupPayout).filter_by(
        group_id=group_id,
        user_id=swap.target_user_id,
        cycle_number=swap.target_cycle_number,
        status="PENDING"
    ).first()
    
    if not requester_payout or not target_payout:
        # One of the turns might have already been processed/paid!
        swap.status = "CANCELLED"
        session.commit()
        raise HTTPException(status_code=400, detail="One or both of these turns have already been processed and cannot be swapped anymore.")

    # 2. Authoritative microbond_core Invariant Re-verification
    rotating_details = session.query(RotatingGroupDetails).filter_by(group_id=group_id).first()
    settings = session.query(GroupGovernanceSettings).filter_by(group_id=group_id).first()
    requester_user = session.get(User, swap.requester_user_id)

    rules = {
        "current_active_cycle": getattr(rotating_details, "current_cycle", 1) or 1,
        "minimum_trust_score": settings.minimum_trust_score or 0 if settings else 0,
        "minimum_kyc_tier": 1,
        "is_rotation_locked": getattr(rotating_details, "is_payout_order_locked", False),
    }
    member_a = {
        "user_id": str(swap.requester_user_id),
        "assigned_cycle": requester_payout.cycle_number,
        "membership_status": "ACTIVE",
        "has_received_payout": False,
        "overdue_obligations_count": session.query(MemberObligation).filter(
            MemberObligation.group_id == group_id,
            MemberObligation.user_id == swap.requester_user_id,
            MemberObligation.status == "LATE"
        ).count(),
        "unpaid_penalties_count": 0,
        "trust_score": requester_user.trust_score if requester_user and requester_user.trust_score else 50,
        "kyc_tier": requester_user.kyc_tier if requester_user and requester_user.kyc_tier else 1,
    }
    member_b = {
        "user_id": str(current_user.id),
        "assigned_cycle": target_payout.cycle_number,
        "membership_status": "ACTIVE",
        "has_received_payout": False,
        "overdue_obligations_count": session.query(MemberObligation).filter(
            MemberObligation.group_id == group_id,
            MemberObligation.user_id == current_user.id,
            MemberObligation.status == "LATE"
        ).count(),
        "unpaid_penalties_count": 0,
        "trust_score": current_user.trust_score or 50,
        "kyc_tier": current_user.kyc_tier or 1,
    }

    val_res = json.loads(validate_turn_swap_eligibility(member_a, member_b, rules))
    if not val_res["is_permitted"]:
        swap.status = "CANCELLED"
        session.commit()
        raise HTTPException(status_code=400, detail=f"Swap rejected by risk engine: {val_res['rejection_reason']}")

    approval_mode = getattr(rotating_details, "turn_swap_approval_mode", "MUTUAL_CONSENT") or "MUTUAL_CONSENT"

    # 3. IF ADMIN APPROVAL IS REQUIRED, GATE THE SWAP
    if approval_mode == "ADMIN_APPROVAL_REQUIRED":
        swap.status = "PENDING_ADMIN_APPROVAL"
        swap.updated_at = utc_now()
        session.commit()

        # Notify the requester that peer accepted, now pending admin review
        requester_user = session.get(User, swap.requester_user_id)
        if requester_user and requester_user.fcm_token:
            send_push_notification(
                token=requester_user.fcm_token,
                title="Swap Agreed — Awaiting Admin Approval ⏳",
                body=f"{current_user.full_name} agreed to swap. The request is now waiting for Group Admin approval.",
                data={"type": "SWAP_PENDING_ADMIN", "group_id": group_id}
            )

        return {
            "status": "success",
            "message": "Turn swap agreed by both members. Awaiting Group Admin final approval.",
            "data": {
                "swap_id": swap.id,
                "status": "PENDING_ADMIN_APPROVAL"
            }
        }

    # 4. PERFORM IMMEDIATE SWAP (MUTUAL CONSENT)
    requester_payout.user_id = swap.target_user_id
    target_payout.user_id = swap.requester_user_id
    
    swap.status = "ACCEPTED"
    swap.updated_at = utc_now()
    
    session.commit()

    # Push: notify the original requester that their swap was accepted
    requester_user = session.get(User, swap.requester_user_id)
    if requester_user and requester_user.fcm_token:
        send_push_notification(
            token=requester_user.fcm_token,
            title="Swap Accepted ✅",
            body=f"{current_user.full_name} accepted your turn swap. Your payout position has been updated.",
            data={"type": "SWAP_ACCEPTED", "group_id": group_id}
        )

    return {"status": "success", "message": "Turn swap successfully completed! Your payout position has been updated."}

