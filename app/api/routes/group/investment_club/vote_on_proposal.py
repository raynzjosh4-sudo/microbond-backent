import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.investment_association import InvestmentClubMemberShare
from app.models.group.chat import GroupPoll, GroupPollVote
from .schemas import VoteProposalRequest
from .helpers import get_club, require_member, now_ms as _now_ms

router = APIRouter()

@router.post("/{group_id}/proposals/{poll_id}/vote", summary="Vote on an investment proposal")
def vote_on_proposal(
    group_id: str,
    poll_id: uuid.UUID,
    request: VoteProposalRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Active member casts vote on an investment proposal.
    If voting_power_logic is PROPORTIONAL, member must own at least 1 share.
    """
    require_member(group_id, current_user, session)
    config, settings = get_club(group_id, session)

    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "INVESTMENT_PROPOSAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Investment proposal poll not found.")

    if poll.status != "OPEN":
        raise HTTPException(status_code=400, detail=f"This proposal is already {poll.status.lower()}.")

    now_ms = _now_ms()
    if poll.expires_at <= now_ms:
        poll.status = "CLOSED"
        session.add(poll)
        session.commit()
        raise HTTPException(status_code=400, detail="This voting poll has expired.")

    vote_val = request.vote.upper()
    if vote_val not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=400, detail="Vote must be APPROVE or REJECT.")

    # Check shareholding if PROPORTIONAL
    if config.voting_power_logic == "PROPORTIONAL":
        member_share = session.exec(
            select(InvestmentClubMemberShare).where(
                InvestmentClubMemberShare.group_id == group_id,
                InvestmentClubMemberShare.user_id == current_user.id
            )
        ).first()
        if not member_share or member_share.shares_owned <= 0:
            raise HTTPException(status_code=400, detail="You must hold at least 1 equity share to vote.")

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
            created_at=now_ms
        )
        session.add(new_vote)

    session.commit()

    return {
        "status": "success",
        "message": f"Vote '{vote_val}' recorded."
    }
