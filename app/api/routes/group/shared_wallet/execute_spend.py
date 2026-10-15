from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.chat import GroupPoll
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .helpers import get_wallet, require_admin, now_ms

router = APIRouter()

@router.post("/{group_id}/execute-spend/{poll_id}", summary="Execute approved disbursement after approval/timelock")
def execute_spend(
    group_id: str,
    poll_id: str,
    amount: int,
    recipient_name: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Executes an approved spend proposal after voting has concluded.
    Deducts balance from the wallet and logs the outflow.
    """
    require_admin(group_id, current_user, session)
    _, op_settings = get_wallet(group_id, session)

    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "SPEND_APPROVAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Spend proposal poll not found.")
    if poll.status != "CLOSED":
        raise HTTPException(status_code=400, detail="Spend has not been fully approved yet.")

    spendable = op_settings.current_balance - op_settings.minimum_balance_floor
    if amount > spendable:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient spendable balance. Remaining spendable is {spendable:,}."
        )

    current_time_ms = now_ms()
    op_settings.current_balance -= amount
    op_settings.total_spent += amount
    op_settings.updated_at = current_time_ms
    session.add(op_settings)
    session.commit()

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"{current_user.full_name} executed approved spend of {amount:,} to {recipient_name}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Funds disbursed successfully.",
        "data": {
            "amount_disbursed": amount,
            "remaining_balance": op_settings.current_balance,
            "total_spent": op_settings.total_spent
        }
    }
