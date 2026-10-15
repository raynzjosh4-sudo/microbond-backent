import json
import time
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import GroupMembership
from app.models.user.user import User
from app.models.group.long_term import TargetSavingsGroupDetails
from app.models.group.chat import GroupPoll
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import EarlyPayoutProposalRequest

router = APIRouter()

@router.post("/{group_id}/request-early-payout", summary="Request Group Vote to End Savings Early")
def request_early_payout(
    group_id: str,
    request: EarlyPayoutProposalRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Launches a group vote in the chat so members can decide whether to end savings early
    and receive their money back.
    """
    # 1. Verify Active Membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member to request early payout.")

    details = session.exec(
        select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
    ).first()
    if not details:
        raise HTTPException(status_code=404, detail="Target savings details not found.")

    if not details.allow_early_payout_by_vote:
        raise HTTPException(status_code=400, detail="This group does not allow early payout votes.")

    if details.is_ended or details.is_paid_out:
        raise HTTPException(status_code=400, detail="This savings group has already ended.")

    # 2. Create a GroupPoll for consensus voting
    now_ms = int(time.time() * 1000)
    expires_at = now_ms + (24 * 3600 * 1000) # 24 hours voting window
    poll = GroupPoll(
        group_id=group_id,
        creator_id=current_user.id,
        question=f"End savings early and receive payouts? Reason: {request.reason}",
        options=json.dumps(["Approve Early Payout", "Keep Saving Until Target Date"]),
        poll_type="EARLY_PAYOUT",
        status="OPEN",
        expires_at=expires_at,
        created_at=now_ms
    )
    session.add(poll)
    session.commit()
    session.refresh(poll)

    # 3. Broadcast Poll to Group Chat
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=json.dumps({
            "poll_id": str(poll.id),
            "question": poll.question,
            "options": ["Approve Early Payout", "Keep Saving Until Target Date"],
            "vote_approval_percentage": details.vote_approval_percentage
        }),
        message_type="VOTE",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Early payout vote proposed and broadcast to chat.",
        "data": {
            "poll_id": str(poll.id),
            "expires_at": poll.expires_at,
            "vote_approval_percentage": details.vote_approval_percentage
        }
    }
