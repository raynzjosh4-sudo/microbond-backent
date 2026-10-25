from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.finance import TurnSwapRequest, utc_now
from app.core.firebase_config import send_push_notification

router = APIRouter()

@router.post("/{group_id}/swaps/{swap_request_id}/reject", summary="Reject a turn swap request")
def reject_turn_swap(
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
        raise HTTPException(status_code=403, detail="Only the targeted user can reject this swap.")
        
    if swap.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Cannot reject a swap that is {swap.status}.")

    swap.status = "REJECTED"
    swap.updated_at = utc_now()
    
    session.commit()

    # Push: notify the original requester that their swap was declined
    requester_user = session.get(User, swap.requester_user_id)
    if requester_user and requester_user.fcm_token:
        send_push_notification(
            token=requester_user.fcm_token,
            title="Swap Declined",
            body=f"{current_user.full_name} declined your turn swap request.",
            data={"type": "SWAP_REJECTED", "group_id": group_id}
        )

    return {"status": "success", "message": "Turn swap rejected."}
