import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.chat import GroupPoll, GroupPollVote
from .schemas import VoteClaimRequest
from .helpers import require_member, now_ms

router = APIRouter()

@router.post("/{group_id}/vote-claim/{poll_id}", summary="Member votes on an emergency claim poll")
def vote_on_claim(
    group_id: str,
    poll_id: uuid.UUID,
    request: VoteClaimRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Active member casts vote ('APPROVE' or 'REJECT') on an active emergency claim poll.
    """
    require_member(group_id, current_user, session)
    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "CLAIM_APPROVAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Claim poll not found.")

    if poll.status != "OPEN":
        raise HTTPException(status_code=400, detail=f"This claim poll is already {poll.status.lower()}.")

    current_time_ms = now_ms()
    if poll.expires_at <= current_time_ms:
        poll.status = "CLOSED"
        session.add(poll)
        session.commit()
        raise HTTPException(status_code=400, detail="This claim poll has expired.")

    vote_val = request.vote.upper()
    if vote_val not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=400, detail="Vote must be APPROVE or REJECT.")

    # Check for existing vote
    existing_vote = session.exec(
        select(GroupPollVote).where(
            GroupPollVote.poll_id == poll_id,
            GroupPollVote.user_id == current_user.id
        )
    ).first()

    if existing_vote:
        existing_vote.selected_option = vote_val
        session.add(existing_vote)
    else:
        new_vote = GroupPollVote(
            poll_id=poll_id,
            user_id=current_user.id,
            selected_option=vote_val,
            created_at=current_time_ms
        )
        session.add(new_vote)

    session.commit()

    return {
        "status": "success",
        "message": f"Vote '{vote_val}' recorded successfully."
    }
