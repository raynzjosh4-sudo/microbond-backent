from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session
from uuid import UUID

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.finance import TurnSwapRequest, GroupPayout, utc_now
from app.models.group.settings import GroupGovernanceSettings
from app.models.group.rotating import RotatingGroupDetails

router = APIRouter(prefix="/api/v1/groups", tags=["Group Payout Turn Swapping"])

class RequestSwapPayload(BaseModel):
    target_user_id: UUID

class SwapResponse(BaseModel):
    swap_request_id: str
    requester_user_id: UUID
    target_user_id: UUID
    requester_cycle_number: int
    target_cycle_number: int
    status: str

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
    
    return swap

@router.post("/{group_id}/swaps/{swap_request_id}/accept", summary="Accept a turn swap request")
def accept_turn_swap(
    group_id: str,
    swap_request_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    swap = session.query(TurnSwapRequest).filter_by(
        swap_request_id=swap_request_id,
        group_id=group_id
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

    # 2. PERFORM THE SWAP
    # Just exchange the user_ids!
    requester_payout.user_id = swap.target_user_id
    target_payout.user_id = swap.requester_user_id
    
    swap.status = "ACCEPTED"
    swap.updated_at = utc_now()
    
    session.commit()
    
    return {"status": "success", "message": "Turn swap successfully completed! Your payout position has been updated."}

@router.post("/{group_id}/swaps/{swap_request_id}/reject", summary="Reject a turn swap request")
def reject_turn_swap(
    group_id: str,
    swap_request_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    swap = session.query(TurnSwapRequest).filter_by(
        swap_request_id=swap_request_id,
        group_id=group_id
    ).first()
    
    if not swap:
        raise HTTPException(status_code=404, detail="Swap request not found.")
        
    if swap.target_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the targeted user can reject this swap.")
        
    if swap.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Cannot reject a swap that is {swap.status}.")

    swap.status = "REJECTED"
    swap.updated_at = utc_now()
    
    session.commit()
    
    return {"status": "success", "message": "Turn swap rejected."}
