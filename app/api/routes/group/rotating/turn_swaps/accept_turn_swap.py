from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.finance import TurnSwapRequest, GroupPayout, utc_now
from app.core.firebase_config import send_push_notification

router = APIRouter()

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
