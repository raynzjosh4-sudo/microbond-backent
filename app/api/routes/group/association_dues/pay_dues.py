import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group
from app.models.user.user import User
from app.models.group.investment_association import AssociationMemberDuesStanding
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import PayDuesRequest
from .helpers import require_member, now_ms as _now_ms, get_association

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/pay-dues", summary="Member pays recurring dues or advance cycles")
def pay_dues(
    group_id: str,
    request: PayDuesRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Member pays dues for one or multiple cycles.
    - Clears arrears and increments prepaid cycles.
    - Updates vault balance.
    - Automatically sweeps to treasury if auto_sweep_trigger is INSTANT.
    """
    require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_association(group_id, session)
    now_ms = _now_ms()

    if not settings.is_active:
        raise HTTPException(status_code=400, detail="Association billing is currently paused or inactive.")

    if request.cycles_count > 1 and not settings.allow_advance_payments:
        raise HTTPException(status_code=400, detail="Advance multi-cycle payments are not permitted by current settings.")

    total_amount = request.cycles_count * config.dues_amount

    # Update member standing
    standing = session.exec(
        select(AssociationMemberDuesStanding).where(
            AssociationMemberDuesStanding.group_id == group_id,
            AssociationMemberDuesStanding.user_id == current_user.id
        )
    ).first()

    cycle_duration_ms = config.billing_cycle_days * 86400 * 1000

    if not standing:
        standing = AssociationMemberDuesStanding(
            group_id=group_id,
            user_id=current_user.id,
            cycles_paid_ahead=request.cycles_count - 1,
            consecutive_missed_cycles=0,
            outstanding_arrears_balance=0,
            is_in_arrears=False,
            is_suspended=False,
            last_payment_date=now_ms,
            next_due_date=now_ms + (request.cycles_count * cycle_duration_ms),
            updated_at=now_ms
        )
    else:
        standing.outstanding_arrears_balance = 0
        standing.is_in_arrears = False
        standing.consecutive_missed_cycles = 0
        standing.is_suspended = False
        standing.cycles_paid_ahead += (request.cycles_count - 1)
        standing.last_payment_date = now_ms
        base_due = max(now_ms, standing.next_due_date)
        standing.next_due_date = base_due + (request.cycles_count * cycle_duration_ms)
        standing.updated_at = now_ms

    session.add(standing)

    # Update collection counters
    settings.total_collected += total_amount
    settings.current_balance += total_amount

    # Instant auto-sweep check
    was_swept = False
    if settings.auto_sweep_trigger == "INSTANT":
        settings.total_swept_to_treasury += total_amount
        settings.current_balance = max(0, settings.current_balance - total_amount)
        was_swept = True

    settings.updated_at = now_ms
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error processing dues payment: {e}")
        raise HTTPException(status_code=500, detail="Database error recording dues payment.")

    sweep_note = " (Auto-swept to external treasury)" if was_swept else ""
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"💳 Dues Paid: {current_user.full_name} paid {total_amount} {group.currency} for {request.cycles_count} cycle(s){sweep_note}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": f"Dues payment of {total_amount} {group.currency} successfully recorded.",
        "data": {
            "amount_paid": total_amount,
            "cycles_paid": request.cycles_count,
            "next_due_date": standing.next_due_date,
            "auto_swept_to_treasury": was_swept,
            "vault_balance": settings.current_balance
        }
    }
