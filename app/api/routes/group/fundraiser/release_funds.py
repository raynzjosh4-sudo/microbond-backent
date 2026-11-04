import secrets
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from sqlalchemy import func

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.chat import GroupPoll, GroupPollVote
from app.models.group.wallet import GroupWallet
from app.models.group.ledger import LedgerEntry
from app.models.group.finance.group_payout import GroupPayout
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.services.websocket_manager import ws_manager
from .helpers import get_campaign, require_admin, now_ms

router = APIRouter()

@router.post("/{group_id}/release-funds", summary="Send the collected money to the destination")
def release_funds(
    group_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Releases the collected funds.
    - If require_multi_signoff is False: admin calls this directly.
    - If require_multi_signoff is True: verifies that an approved FUND_RELEASE poll exists
      with at least `signoff_count_required` approving votes.
    """
    require_admin(group_id, current_user, session)
    config, stats = get_campaign(group_id, session)

    if stats.is_paid_out:
        raise HTTPException(status_code=400, detail="Funds have already been released for this fundraiser.")
    if stats.total_raised <= 0:
        raise HTTPException(status_code=400, detail="No funds have been collected yet.")

    # If multi-signoff required, verify an approved FUND_RELEASE poll exists
    if config.require_multi_signoff:
        poll = session.exec(
            select(GroupPoll).where(
                GroupPoll.group_id == group_id,
                GroupPoll.poll_type == "FUND_RELEASE"
            ).order_by(GroupPoll.created_at.desc())
        ).first()
        if not poll:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"This fundraiser requires {config.signoff_count_required} signers to approve "
                    "before funds can be released. Please use request-signoff first."
                )
            )

        if poll.status != "CLOSED":
            approve_votes = session.exec(
                select(func.count()).select_from(GroupPollVote).where(
                    GroupPollVote.poll_id == poll.id,
                    GroupPollVote.selected_option == "Approve Release"
                )
            ).one()
            if approve_votes < config.signoff_count_required:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"This fundraiser requires {config.signoff_count_required} approvals. "
                        f"Only {approve_votes} approval(s) recorded so far."
                    )
                )
            poll.status = "CLOSED"
            session.add(poll)

    current_time = now_ms()

    # Deduct from group pooled funds
    wallet = session.exec(select(GroupWallet).where(GroupWallet.group_id == group_id)).first()
    if wallet:
        wallet.pooled_funds = max(0, (wallet.pooled_funds or 0) - stats.total_raised)
        wallet.updated_at = current_time
        session.add(wallet)

    # Record payout ledger entry
    payout_ledger = LedgerEntry(
        group_id=group_id,
        user_id=current_user.id,
        source_account="GROUP_POOLED",
        destination_account=config.nominated_account_id or config.payout_destination_type,
        amount=stats.total_raised,
        transaction_type="PAYOUT",
        external_reference_id=f"PAY-{secrets.token_hex(6).upper()}",
        status="SETTLED",
        settled_at=current_time
    )
    session.add(payout_ledger)

    # Record GroupPayout tracking row
    payout = GroupPayout(
        group_id=group_id,
        user_id=current_user.id,
        amount_expected=stats.total_raised,
        amount_received=stats.total_raised,
        status="COMPLETED",
        payout_date=current_time,
        created_at=current_time
    )
    session.add(payout)

    # Mark as paid out
    stats.is_paid_out = True
    stats.is_active = False
    stats.updated_at = current_time
    session.add(stats)
    session.commit()

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=(
            f"🎉 {current_user.full_name} has released the collected funds "
            f"({stats.total_raised:,} UGX) to the designated recipient ({config.payout_destination_type})."
        ),
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    try:
        background_tasks.add_task(
            ws_manager.broadcast_to_group,
            group_id,
            {
                "event_type": "FUNDRAISER_PAID_OUT",
                "group_id": group_id,
                "total_released": stats.total_raised,
                "is_paid_out": True,
                "is_active": False
            }
        )
    except Exception:
        pass

    return {
        "status": "success",
        "message": "Funds released successfully.",
        "data": {
            "total_released": stats.total_raised,
            "payout_destination_type": config.payout_destination_type,
            "nominated_account_id": config.nominated_account_id
        }
    }
