import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group
from app.models.user.user import User
from app.models.group.investment_association import InvestmentClubMemberShare
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import BuySharesRequest
from .helpers import get_club, require_member, now_ms as _now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/buy-shares", summary="Member purchases equity shares in the club")
def buy_shares(
    group_id: str,
    request: BuySharesRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Member purchases equity shares.
    - Calculates total cost based on fixed share_unit_price.
    - Credits club vault balance and increases total_shares_issued.
    - Updates member's personal share balance.
    """
    require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_club(group_id, session)
    now_ms = _now_ms()

    if not settings.is_active:
        raise HTTPException(status_code=400, detail="The investment club is currently inactive or closed to share purchases.")

    total_cost = request.shares_count * config.share_unit_price

    # 1. Update or create member share entry
    member_share = session.exec(
        select(InvestmentClubMemberShare).where(
            InvestmentClubMemberShare.group_id == group_id,
            InvestmentClubMemberShare.user_id == current_user.id
        )
    ).first()

    if not member_share:
        member_share = InvestmentClubMemberShare(
            group_id=group_id,
            user_id=current_user.id,
            shares_owned=request.shares_count,
            total_invested=total_cost,
            last_dividend_received=0,
            created_at=now_ms,
            updated_at=now_ms
        )
    else:
        member_share.shares_owned += request.shares_count
        member_share.total_invested += total_cost
        member_share.updated_at = now_ms

    session.add(member_share)

    # 2. Update club settings & counters
    settings.total_shares_issued += request.shares_count
    settings.current_balance += total_cost
    settings.updated_at = now_ms
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error buying shares: {e}")
        raise HTTPException(status_code=500, detail="Database error recording share purchase.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"ðŸ“ˆ {current_user.full_name} purchased {request.shares_count} shares ({total_cost} {group.currency}).",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": f"Successfully purchased {request.shares_count} shares.",
        "data": {
            "shares_bought": request.shares_count,
            "total_cost": total_cost,
            "my_total_shares": member_share.shares_owned,
            "club_total_shares": settings.total_shares_issued,
            "vault_balance": settings.current_balance
        }
    }

