from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import TurnSwapRequest, GroupPayout
from app.core.firebase_config import send_push_notification
from app.utils.time.now_epoch_ms import now_epoch_ms

router = APIRouter()


class AdminReviewSwapPayload(BaseModel):
    action: str = Field(..., description="APPROVE or REJECT")
    rejection_reason: Optional[str] = Field(default=None, description="Reason if rejecting the swap")


@router.post("/{group_id}/swaps/{swap_request_id}/admin-review", summary="Admin Review & Finalize Turn Swap")
def admin_review_turn_swap(
    group_id: str,
    swap_request_id: str,
    payload: AdminReviewSwapPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Allows the Group Admin to approve or reject a turn swap when
    turn_swap_approval_mode is ADMIN_APPROVAL_REQUIRED.
    """
    # 1. Authorize: caller must be Admin
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can review turn swap requests.")

    # 2. Find swap request (supports UUID swap_request_id or numeric id)
    is_numeric = swap_request_id.isdigit()
    swap = session.exec(
        select(TurnSwapRequest).where(
            TurnSwapRequest.group_id == group_id,
            (TurnSwapRequest.swap_request_id == swap_request_id) | (TurnSwapRequest.id == (int(swap_request_id) if is_numeric else -1))
        )
    ).first()

    if not swap:
        raise HTTPException(status_code=404, detail="Turn swap request not found.")

    if swap.status != "PENDING_ADMIN_APPROVAL":
        raise HTTPException(status_code=400, detail=f"Cannot review swap with status '{swap.status}'.")

    requester_user = session.get(User, swap.requester_user_id)
    target_user = session.get(User, swap.target_user_id)

    if payload.action.upper() == "REJECT":
        swap.status = "REJECTED"
        swap.updated_at = now_epoch_ms()
        session.commit()

        # Notify members of rejection
        reason = payload.rejection_reason or "Declined by Group Admin"
        for u in [requester_user, target_user]:
            if u and u.fcm_token:
                send_push_notification(
                    token=u.fcm_token,
                    title="Turn Swap Rejected ❌",
                    body=f"Your turn swap request was declined by the Admin: {reason}",
                    data={"type": "SWAP_REJECTED", "group_id": group_id}
                )

        return {"status": "success", "message": "Turn swap successfully rejected by Admin."}

    elif payload.action.upper() == "APPROVE":
        # 3. Find payouts and execute the swap
        requester_payout = session.exec(
            select(GroupPayout).where(
                GroupPayout.group_id == group_id,
                GroupPayout.user_id == swap.requester_user_id,
                GroupPayout.cycle_number == swap.requester_cycle_number,
                GroupPayout.status == "PENDING"
            )
        ).first()

        target_payout = session.exec(
            select(GroupPayout).where(
                GroupPayout.group_id == group_id,
                GroupPayout.user_id == swap.target_user_id,
                GroupPayout.cycle_number == swap.target_cycle_number,
                GroupPayout.status == "PENDING"
            )
        ).first()

        if not requester_payout or not target_payout:
            swap.status = "CANCELLED"
            session.commit()
            raise HTTPException(status_code=400, detail="One or both of these turns are no longer eligible for swap.")

        # Exchange the user_ids
        requester_payout.user_id = swap.target_user_id
        target_payout.user_id = swap.requester_user_id

        swap.status = "ACCEPTED"
        swap.updated_at = now_epoch_ms()

        # Event 19: Insert Chat Confirmation into Group Thread
        import uuid
        from app.models.group.chat import GroupChatMessage
        req_u = session.get(User, swap.requester_user_id)
        tar_u = session.get(User, swap.target_user_id)
        requester_name = req_u.full_name if req_u else "Requester"
        target_name = tar_u.full_name if tar_u else "Target"
        c1 = swap.requester_cycle_number
        c2 = swap.target_cycle_number

        chat_msg = GroupChatMessage(
            client_message_id=str(uuid.uuid4()),
            group_id=group_id,
            sender_id="SYSTEM",
            message_type="SYSTEM_EVENT",
            message_text=f"🔄 Turn Swap Confirmed: {requester_name} (was Turn {c1}) and {target_name} (was Turn {c2}) have successfully swapped payout positions.",
            status="SENT"
        )
        session.add(chat_msg)

        session.add(requester_payout)
        session.add(target_payout)
        session.add(swap)
        session.commit()

        # Event 19: Push broadcast to all group members
        try:
            from app.services.push_notifications import notify_all_group_members_sync
            notify_all_group_members_sync(
                group_id=group_id,
                sender_id="SYSTEM",
                title="🔄 Turn Swap Confirmed",
                body=f"{requester_name} and {target_name} have swapped payout positions (Turn {c1} & Turn {c2}).",
                data={"route": "rotation_schedule", "group_id": group_id}
            )
        except Exception as push_err:
            pass

        return {
            "status": "success",
            "message": "Turn swap approved and executed successfully by Admin.",
            "data": {
                "swap_id": swap.id,
                "status": "ACCEPTED"
            }
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'APPROVE' or 'REJECT'.")
