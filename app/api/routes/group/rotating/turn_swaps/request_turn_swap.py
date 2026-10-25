import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.finance import TurnSwapRequest, GroupPayout, MemberObligation
from app.models.group.settings import GroupGovernanceSettings
from app.models.group.rotating import RotatingGroupDetails
from app.core.firebase_config import send_push_notification
from app.core.microbond_core import validate_turn_swap_eligibility
from .schemas import RequestSwapPayload, SwapResponse

router = APIRouter()

@router.post("/{group_id}/swaps/request", response_model=SwapResponse, summary="Request a turn swap")
def request_turn_swap(
    group_id: str,
    payload: RequestSwapPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Check if group allows turn swapping
    rotating_details = session.query(RotatingGroupDetails).filter_by(group_id=group_id).first()
    if not rotating_details:
        raise HTTPException(status_code=400, detail="Not a rotating savings group.")

    settings = session.query(GroupGovernanceSettings).filter_by(group_id=group_id).first()
    if (settings and not settings.allow_turn_swaps) or not getattr(rotating_details, "allow_turn_swaps", True):
        raise HTTPException(status_code=403, detail="This group does not allow turn swapping.")

    # 2. Find pending payouts for both users
    requester_payout = session.query(GroupPayout).filter(
        GroupPayout.group_id == group_id,
        GroupPayout.user_id == current_user.id,
        GroupPayout.status == "PENDING"
    ).order_by(GroupPayout.cycle_number.asc()).first()
    
    if not requester_payout:
        raise HTTPException(status_code=400, detail="You do not have any pending payouts to swap.")
        
    target_payout = session.query(GroupPayout).filter(
        GroupPayout.group_id == group_id,
        GroupPayout.user_id == payload.target_user_id,
        GroupPayout.status == "PENDING"
    ).order_by(GroupPayout.cycle_number.asc()).first()
    
    if not target_payout:
        raise HTTPException(status_code=400, detail="Target user has no pending payouts to swap.")

    # 2b. Enforce Guarantor check for early turn swaps
    if getattr(rotating_details, "require_guarantor", False):
        from app.models.group.finance import GuarantorPledge
        total_cycles = rotating_details.number_of_cycles or 10
        half_mark = (total_cycles + 1) // 2
        for moving_user_id, destination_cycle in [(current_user.id, target_payout.cycle_number), (payload.target_user_id, requester_payout.cycle_number)]:
            if destination_cycle <= half_mark:
                pledge = session.query(GuarantorPledge).filter(
                    GuarantorPledge.group_id == group_id,
                    GuarantorPledge.borrower_user_id == moving_user_id,
                    GuarantorPledge.status == "ACTIVE"
                ).first()
                if not pledge:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot swap into early Round {destination_cycle} without an active guarantor."
                    )

    # 3. Check if an active swap request already exists between these cycles
    existing_swap = session.query(TurnSwapRequest).filter(
        TurnSwapRequest.group_id == group_id,
        TurnSwapRequest.requester_cycle_number == requester_payout.cycle_number,
        TurnSwapRequest.target_cycle_number == target_payout.cycle_number,
        TurnSwapRequest.status == "PENDING"
    ).first()
    
    if existing_swap:
        raise HTTPException(status_code=400, detail="A pending swap request already exists for these turns.")


    # 4. Authoritative microbond_core Invariant Verification
    target_user = session.get(User, payload.target_user_id)
    rules = {
        "current_active_cycle": getattr(rotating_details, "current_cycle", 1) or 1,
        "minimum_trust_score": settings.minimum_trust_score or 0 if settings else 0,
        "minimum_kyc_tier": 1,
        "is_rotation_locked": getattr(rotating_details, "is_payout_order_locked", False),
    }
    member_a = {
        "user_id": str(current_user.id),
        "assigned_cycle": requester_payout.cycle_number,
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
    member_b = {
        "user_id": str(payload.target_user_id),
        "assigned_cycle": target_payout.cycle_number,
        "membership_status": "ACTIVE",
        "has_received_payout": False,
        "overdue_obligations_count": session.query(MemberObligation).filter(
            MemberObligation.group_id == group_id,
            MemberObligation.user_id == payload.target_user_id,
            MemberObligation.status == "LATE"
        ).count(),
        "unpaid_penalties_count": 0,
        "trust_score": target_user.trust_score if target_user and target_user.trust_score else 50,
        "kyc_tier": target_user.kyc_tier if target_user and target_user.kyc_tier else 1,
    }

    val_res = json.loads(validate_turn_swap_eligibility(member_a, member_b, rules))
    if not val_res["is_permitted"]:
        raise HTTPException(status_code=400, detail=val_res["rejection_reason"])


    # 4. Create the Swap Request
    swap = TurnSwapRequest(
        group_id=group_id,
        requester_user_id=current_user.id,
        target_user_id=payload.target_user_id,
        requester_cycle_number=requester_payout.cycle_number,
        target_cycle_number=target_payout.cycle_number,
        status="PENDING"
    )
    
    session.add(swap)
    session.commit()
    session.refresh(swap)

    # Push: notify the target that a swap request is waiting for their response
    target_user = session.get(User, payload.target_user_id)
    if target_user and target_user.fcm_token:
        send_push_notification(
            token=target_user.fcm_token,
            title="Turn Swap Request 🔄",
            body=f"{current_user.full_name} wants to swap their payout turn with yours. Tap to review.",
            data={"type": "SWAP_REQUEST", "group_id": group_id, "swap_id": swap.swap_request_id}
        )

    return swap
