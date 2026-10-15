import logging
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group
from app.models.user.user import User
from app.models.group.chat import GroupPoll
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import CreateInvestmentProposalRequest
from .helpers import get_club, require_member, now_ms as _now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/proposals/create", summary="Propose funding an external asset")
def create_investment_proposal(
    group_id: str,
    request: CreateInvestmentProposalRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Submits an investment proposal to deploy capital from the club vault into an asset.
    Opens a voting poll for the club.
    """
    require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_club(group_id, session)
    now_ms = _now_ms()

    if settings.current_balance < request.required_capital:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient uninvested vault capital. Vault has {settings.current_balance} {group.currency}, required is {request.required_capital} {group.currency}."
        )

    poll_id = uuid.uuid4()
    poll = GroupPoll(
        id=poll_id,
        group_id=group_id,
        creator_id=current_user.id,
        question=f"Investment Proposal: {request.asset_name} ({request.required_capital} {group.currency} for {request.asset_type})",
        options=json.dumps(["APPROVE", "REJECT"]),
        poll_type="INVESTMENT_PROPOSAL",
        status="OPEN",
        expires_at=now_ms + (72 * 3600 * 1000),
        created_at=now_ms
    )
    session.add(poll)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error creating proposal: {e}")
        raise HTTPException(status_code=500, detail="Database error creating proposal.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=(
            f"ðŸ’¡ New Investment Proposal: {current_user.full_name} proposed investing {request.required_capital} {group.currency} "
            f"in '{request.asset_name}'. Please review and vote before the poll closes."
        ),
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Investment proposal created and opened for voting.",
        "data": {
            "poll_id": str(poll_id),
            "asset_name": request.asset_name,
            "required_capital": request.required_capital,
            "expires_at": poll.expires_at
        }
    }

