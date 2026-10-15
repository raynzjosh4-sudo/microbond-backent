import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group
from app.models.user.user import User
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import TriggerTreasurySweepRequest
from .helpers import now_ms as _now_ms, require_admin, get_association

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/trigger-sweep", summary="Admin manually sweeps vault balance to association treasury")
def trigger_treasury_sweep(
    group_id: str,
    request: TriggerTreasurySweepRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin pushes accumulated dues balance from the vault to the verified association external treasury account.
    """
    require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_association(group_id, session)
    now_ms = _now_ms()

    sweep_amount = request.amount if request.amount is not None else settings.current_balance

    if sweep_amount <= 0:
        raise HTTPException(status_code=400, detail="No funds available in the vault to sweep.")

    if settings.current_balance < sweep_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Requested sweep of {sweep_amount} {group.currency} exceeds vault balance of {settings.current_balance} {group.currency}."
        )

    settings.current_balance = max(0, settings.current_balance - sweep_amount)
    settings.total_swept_to_treasury += sweep_amount
    settings.updated_at = now_ms
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error sweeping funds: {e}")
        raise HTTPException(status_code=500, detail="Database error executing treasury sweep.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"🏛️ Treasury Sweep: {sweep_amount} {group.currency} transferred to Association treasury account.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": f"Successfully swept {sweep_amount} {group.currency} to treasury.",
        "data": {
            "amount_swept": sweep_amount,
            "destination_treasury_account": config.treasury_account_id,
            "remaining_vault_balance": settings.current_balance,
            "total_swept_to_date": settings.total_swept_to_treasury
        }
    }
