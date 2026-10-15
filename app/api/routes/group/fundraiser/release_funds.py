from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.chat import GroupPoll
from app.api.routes.group.chat.messages import broadcast_system_message_sync
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
    - If require_multi_signoff is True: checks that an approved FUND_RELEASE poll exists.
    """
    require_admin(group_id, current_user, session)
    config, stats = get_campaign(group_id, session)

    if stats.is_paid_out:
        raise HTTPException(status_code=400, detail="Funds have already been released for this fundraiser.")
    if stats.total_raised <= 0:
        raise HTTPException(status_code=400, detail="No funds have been collected yet.")

    # If multi-signoff required, verify an approved FUND_RELEASE poll exists
    if config.require_multi_signoff:
        approved_poll = session.exec(
            select(GroupPoll).where(
                GroupPoll.group_id == group_id,
                GroupPoll.poll_type == "FUND_RELEASE",
                GroupPoll.status == "CLOSED"
            )
        ).first()
        if not approved_poll:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"This fundraiser requires {config.signoff_count_required} signers to approve "
                    "before funds can be released. Please use request-signoff first."
                )
            )

    # Mark as paid out
    stats.is_paid_out = True
    stats.is_active = False
    stats.updated_at = now_ms()
    session.add(stats)
    session.commit()

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=(
            f"{current_user.full_name} has released the collected funds "
            f"({stats.total_raised:,} {config.payout_destination_type}) to the designated account."
        ),
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Funds released successfully.",
        "data": {
            "total_released": stats.total_raised,
            "payout_destination_type": config.payout_destination_type,
            "nominated_account_id": config.nominated_account_id
        }
    }
