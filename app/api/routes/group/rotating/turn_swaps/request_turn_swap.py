from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.finance import TurnSwapRequest, GroupPayout
from app.models.group.settings import GroupGovernanceSettings
from app.models.group.rotating import RotatingGroupDetails
from app.core.firebase_config import send_push_notification
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
    settings = session.query(GroupGovernanceSettings).filter_by(group_id=group_id).first()
    if settings and not settings.allow_turn_swaps:
        raise HTTPException(status_code=403, detail="This group does not allow turn swapping.")
        
    rotating_details = session.query(RotatingGroupDetails).filter_by(group_id=group_id).first()
    if not rotating_details:
        raise HTTPException(status_code=400, detail="Not a rotating savings group.")

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

    # 3. Check if an active swap request already exists between these cycles
    existing_swap = session.query(TurnSwapRequest).filter(
        TurnSwapRequest.group_id == group_id,
        TurnSwapRequest.requester_cycle_number == requester_payout.cycle_number,
        TurnSwapRequest.target_cycle_number == target_payout.cycle_number,
        TurnSwapRequest.status == "PENDING"
    ).first()
    
    if existing_swap:
        raise HTTPException(status_code=400, detail="A pending swap request already exists for these turns.")

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
