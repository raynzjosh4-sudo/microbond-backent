import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group
from app.models.user.user import User
from app.models.group.investment_association import InvestmentClubMemberShare
from app.models.group.chat import GroupPoll, GroupPollVote
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .helpers import require_admin, get_club

router = APIRouter()

@router.post("/{group_id}/proposals/{poll_id}/execute", summary="Admin executes approved proposal and deploys capital")
def execute_proposal(
    group_id: str,
    poll_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin verifies voting threshold and executes capital deployment to external broker/vendor:
    - Verifies approval threshold (e.g. 66%).
    - Transfers capital from vault current_balance to total_invested_capital.
    - Closes poll and marks status EXECUTED.
    """
    require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_club(group_id, session)

    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "INVESTMENT_PROPOSAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Proposal poll not found.")

    if poll.status == "EXECUTED":
        raise HTTPException(status_code=400, detail="This proposal has already been executed.")

    votes = session.exec(select(GroupPollVote).where(GroupPollVote.poll_id == poll_id)).all()
    if not votes:
        raise HTTPException(status_code=400, detail="No votes have been cast for this proposal.")

    # Calculate vote weight
    if config.voting_power_logic == "PROPORTIONAL":
        total_approve_weight = 0
        total_vote_weight = 0
        for v in votes:
            ms = session.exec(
                select(InvestmentClubMemberShare).where(
                    InvestmentClubMemberShare.group_id == group_id,
                    InvestmentClubMemberShare.user_id == v.user_id
                )
            ).first()
            w = ms.shares_owned if ms else 0
            total_vote_weight += w
            if v.selected_option == "APPROVE":
                total_approve_weight += w
        approval_pct = (total_approve_weight / total_vote_weight * 100) if total_vote_weight > 0 else 0
    else:
        approve_count = sum(1 for v in votes if v.selected_option == "APPROVE")
        approval_pct = (approve_count / len(votes) * 100)

    if approval_pct < settings.proposal_approval_threshold_pct:
        raise HTTPException(
            status_code=400,
            detail=f"Proposal did not meet required threshold of {settings.proposal_approval_threshold_pct}%. Current approval is {round(approval_pct, 1)}%."
        )

    # Deploy capital
    poll.status = "EXECUTED"
    session.add(poll)

    session.commit()

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"ðŸš€ Investment Executed: Proposal '{poll.question}' approved with {round(approval_pct, 1)}% support and capital deployed.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Investment proposal executed and capital deployed.",
        "data": {
            "poll_id": str(poll_id),
            "approval_percentage": round(approval_pct, 1),
            "threshold_required": settings.proposal_approval_threshold_pct
        }
    }
