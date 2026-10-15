import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.models.group.investment_association import InvestmentClubMemberShare
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import TransferSharesRequest
from .helpers import get_club, require_member, now_ms as _now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/shares/transfer", summary="Peer-to-peer share transfer between active members")
def transfer_shares(
    group_id: str,
    request: TransferSharesRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Allows a member to sell or transfer their equity shares directly to another active member.
    """
    require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_club(group_id, session)
    now_ms = _now_ms()

    if not settings.allow_internal_share_transfers:
        raise HTTPException(status_code=400, detail="Internal peer-to-peer share transfers are disabled for this club.")

    try:
        recipient_id = uuid.UUID(request.recipient_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recipient user ID format.")

    recipient_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == recipient_id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not recipient_membership:
        raise HTTPException(status_code=404, detail="Recipient is not an active member of this investment club.")

    sender_share = session.exec(
        select(InvestmentClubMemberShare).where(
            InvestmentClubMemberShare.group_id == group_id,
            InvestmentClubMemberShare.user_id == current_user.id
        )
    ).first()

    if not sender_share or sender_share.shares_owned < request.shares_count:
        available = sender_share.shares_owned if sender_share else 0
        raise HTTPException(status_code=400, detail=f"Insufficient shares. You hold {available} shares, requested {request.shares_count}.")

    # Deduct from sender
    sender_share.shares_owned -= request.shares_count
    sender_share.updated_at = now_ms
    session.add(sender_share)

    # Credit recipient
    recipient_share = session.exec(
        select(InvestmentClubMemberShare).where(
            InvestmentClubMemberShare.group_id == group_id,
            InvestmentClubMemberShare.user_id == recipient_id
        )
    ).first()

    if not recipient_share:
        recipient_share = InvestmentClubMemberShare(
            group_id=group_id,
            user_id=recipient_id,
            shares_owned=request.shares_count,
            total_invested=request.shares_count * config.share_unit_price,
            last_dividend_received=0,
            created_at=now_ms,
            updated_at=now_ms
        )
    else:
        recipient_share.shares_owned += request.shares_count
        recipient_share.updated_at = now_ms

    session.add(recipient_share)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error transferring shares: {e}")
        raise HTTPException(status_code=500, detail="Database error executing share transfer.")

    recipient_user = session.exec(select(User).where(User.id == recipient_id)).first()
    recipient_name = recipient_user.full_name if recipient_user else "Member"

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"ðŸ¤ Share Transfer: {current_user.full_name} transferred {request.shares_count} shares to {recipient_name}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": f"Successfully transferred {request.shares_count} shares to {recipient_name}.",
        "data": {
            "shares_transferred": request.shares_count,
            "sender_remaining_shares": sender_share.shares_owned,
            "recipient_total_shares": recipient_share.shares_owned
        }
    }

