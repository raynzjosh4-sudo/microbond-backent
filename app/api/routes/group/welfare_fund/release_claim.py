import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group
from app.models.user.user import User
from app.models.group.chat import GroupPoll, GroupPollVote
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .helpers import get_welfare_fund, require_admin, now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/release-claim/{poll_id}", summary="Admin executes release of approved claim")
def release_claim(
    group_id: str,
    poll_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin finalizes and releases funds for an approved emergency claim poll:
    - Counts votes to verify majority approval.
    - Closes poll and marks status EXECUTED.
    - Deducts amount from pool current_balance and increments total_paid_out.
    - Broadcasts payout event to group chat.
    """
    require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_welfare_fund(group_id, session)

    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "CLAIM_APPROVAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Claim poll not found.")

    if poll.status == "EXECUTED":
        raise HTTPException(status_code=400, detail="This claim has already been released.")

    # Tally votes
    votes = session.exec(select(GroupPollVote).where(GroupPollVote.poll_id == poll_id)).all()
    approve_count = sum(1 for v in votes if v.selected_option == "APPROVE")
    reject_count = sum(1 for v in votes if v.selected_option == "REJECT")

    # If MAJORITY_VOTE policy, require approve > reject
    if config.claim_approval_policy == "MAJORITY_VOTE" and approve_count <= reject_count:
        raise HTTPException(
            status_code=400,
            detail=f"Claim is not approved by majority. Approvals: {approve_count}, Rejections: {reject_count}."
        )

    # Parse amount from question
    claimant = session.exec(select(User).where(User.id == poll.creator_id)).first()
    claimant_name = claimant.full_name if claimant else "Member"

    # Mark poll as executed
    poll.status = "EXECUTED"
    session.add(poll)

    # Extract or estimate amount (or default to max allowable/claim question)
    amount = min(settings.current_balance, config.max_claim_amount_per_incident)
    settings.current_balance = max(0, settings.current_balance - amount)
    settings.total_paid_out += amount
    settings.updated_at = now_ms()
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error releasing claim: {e}")
        raise HTTPException(status_code=500, detail="Database error releasing claim.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"💚 Emergency Claim Approved & Released: Payout released to {claimant_name}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Claim payout successfully released.",
        "data": {
            "poll_id": str(poll_id),
            "amount_paid": amount,
            "remaining_fund_balance": settings.current_balance,
            "total_paid_out": settings.total_paid_out
        }
    }
