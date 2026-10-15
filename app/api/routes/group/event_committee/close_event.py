import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group
from app.models.user.user import User
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .helpers import get_event_committee, require_admin, now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/close-event", summary="Admin closes committee after event completes")
def close_event(
    group_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Closes event committee collections:
    - Sets is_active = False
    - Evaluates excess funds according to excess_funds_action
      (GIFT_TO_BENEFICIARY, PROPORTIONAL_REFUND, ROLLOVER_TO_NEW_EVENT)
    - Broadcasts financial closure summary to group chat
    """
    require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_event_committee(group_id, session)

    if not settings.is_active:
        raise HTTPException(status_code=400, detail="Event committee is already closed.")

    settings.is_active = False
    settings.updated_at = now_ms()
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error closing event: {e}")
        raise HTTPException(status_code=500, detail="Database error closing event committee.")

    excess_balance = settings.current_balance
    action_description = {
        "GIFT_TO_BENEFICIARY": "Surplus funds will be gifted directly to the event celebrant/beneficiary.",
        "PROPORTIONAL_REFUND": "Surplus funds will be returned proportionally to contributors.",
        "ROLLOVER_TO_NEW_EVENT": "Surplus funds will rollover into a future committee fund."
    }.get(config.excess_funds_action, "Surplus funds handled per committee constitution.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=(
            f"🏁 Event Committee Closed: Collections are now finalized. "
            f"Total Disbursed: {settings.total_disbursed} {group.currency}. "
            f"Excess Balance: {excess_balance} {group.currency}. {action_description}"
        ),
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Event Committee closed successfully.",
        "data": {
            "total_disbursed": settings.total_disbursed,
            "remaining_surplus": excess_balance,
            "excess_funds_action": config.excess_funds_action,
            "action_policy": action_description
        }
    }
