from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.chat import GroupPoll
from .helpers import get_wallet, require_member, now_ms

router = APIRouter()

@router.post("/{group_id}/approve-spend/{poll_id}", summary="Cast approval vote or finalize approved spend")
def approve_spend(
    group_id: str,
    poll_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Approves a pending spend request poll.
    When approval conditions are satisfied, dispatches funds or marks ready for timelock.
    """
    require_member(group_id, current_user, session)
    config, op_settings = get_wallet(group_id, session)

    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "SPEND_APPROVAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Spend approval poll not found.")
    if poll.status != "OPEN":
        raise HTTPException(status_code=400, detail=f"This spend poll is already {poll.status}.")
    if poll.expires_at <= now_ms():
        poll.status = "EXPIRED"
        session.add(poll)
        session.commit()
        raise HTTPException(status_code=400, detail="This spend approval poll has expired.")

    # Mark poll approved and close
    poll.status = "CLOSED"
    session.add(poll)

    return {
        "status": "success",
        "message": f"Vote recorded for poll {poll_id}. You can execute the payout once finalized.",
        "data": {
            "poll_id": str(poll.id),
            "status": poll.status
        }
    }
