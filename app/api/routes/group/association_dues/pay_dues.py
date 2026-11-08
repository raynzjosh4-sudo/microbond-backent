import json
import logging
import secrets
from typing import Any, Dict, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, BackgroundTasks, Query
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation
from app.models.group.wallet import GroupWallet
from app.models.group.ledger import LedgerEntry
from app.models.user.user import User
from app.models.group.investment_association import (
    AssociationDuesConfig,
    AssociationDuesOperationalSettings,
    AssociationMemberDuesStanding,
)
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import PayDuesRequest
from .helpers import require_member, now_ms as _now_ms, get_association

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_body_dict(raw_body: Any) -> Dict[str, Any]:
    if isinstance(raw_body, dict):
        return raw_body
    if isinstance(raw_body, str):
        try:
            parsed = json.loads(raw_body)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def execute_obligation_payment(
    session: Session,
    current_user: User,
    obligation_id: Optional[str] = None,
    body_data: Optional[Dict[str, Any]] = None,
    is_cover_default: bool = False,
) -> Dict[str, Any]:
    now_ms = _now_ms()
    data = body_data or {}

    ob_id_raw = obligation_id or data.get("obligation_id") or data.get("obligationId") or data.get("id")
    group_id = data.get("group_id") or data.get("groupId")
    amount_raw = data.get("amount")
    payment_method = data.get("method") or data.get("payment_method") or ("GUARANTOR_COVER" if is_cover_default else "MOBILE_MONEY")
    cycles_count = int(data.get("cycles_count") or 1)

    obligation: Optional[MemberObligation] = None
    if ob_id_raw is not None:
        try:
            ob_int = int(str(ob_id_raw))
            obligation = session.exec(
                select(MemberObligation).where(MemberObligation.id == ob_int)
            ).first()
        except (ValueError, TypeError):
            obligation = None

    if not obligation and group_id:
        obligation = session.exec(
            select(MemberObligation)
            .where(
                MemberObligation.group_id == str(group_id),
                MemberObligation.user_id == current_user.id,
                MemberObligation.status != "PAID",
            )
            .order_by(MemberObligation.cycle_number.asc())
        ).first()

    if not obligation:
        obligation = session.exec(
            select(MemberObligation)
            .where(
                MemberObligation.user_id == current_user.id,
                MemberObligation.status != "PAID",
            )
            .order_by(MemberObligation.id.desc())
        ).first()

    if obligation:
        resolved_group_id = obligation.group_id
        membership = session.exec(
            select(GroupMembership).where(
                GroupMembership.group_id == resolved_group_id,
                GroupMembership.user_id == current_user.id,
            )
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="You must be a member of this group to pay obligations.")

        remaining = max(0.0, float(obligation.amount_due or 0) - float(obligation.amount_paid or 0))
        pay_amount = float(amount_raw) if (amount_raw is not None and float(amount_raw) > 0) else (remaining if remaining > 0 else float(obligation.amount_due or 0))

        obligation.amount_paid = float(obligation.amount_paid or 0) + pay_amount
        if obligation.amount_paid >= float(obligation.amount_due or 0):
            obligation.status = "PAID"
        elif obligation.amount_paid > 0:
            obligation.status = "PARTIAL"
        obligation.updated_at = now_ms
        session.add(obligation)

        wallet = session.exec(select(GroupWallet).where(GroupWallet.group_id == resolved_group_id)).first()
        if wallet:
            wallet.pooled_funds = float(wallet.pooled_funds or 0) + pay_amount
            wallet.updated_at = now_ms
            session.add(wallet)

        group = session.exec(select(Group).where(Group.group_id == resolved_group_id)).first()
        if group:
            group.total_balance = int(group.total_balance or 0) + int(pay_amount)
            group.updated_at = now_ms
            session.add(group)

        membership.total_contributed = int(membership.total_contributed or 0) + int(pay_amount)
        session.add(membership)

        ref_id = data.get("client_reference") or f"OBL-{secrets.token_hex(6).upper()}"
        ledger_entry = LedgerEntry(
            group_id=resolved_group_id,
            user_id=current_user.id,
            obligation_id=obligation.id,
            source_account=str(payment_method),
            destination_account="GROUP_POOLED",
            amount=int(pay_amount),
            currency=(group.currency if group and group.currency else "UGX"),
            transaction_type="GUARANTOR_COVER" if is_cover_default else "DEPOSIT",
            external_reference_id=ref_id,
            status="SETTLED",
            created_at=now_ms,
            settled_at=now_ms,
        )
        session.add(ledger_entry)
        session.commit()
        session.refresh(obligation)
        if not is_cover_default:
            from app.services.push_notifications import notify_all_group_members_sync

            member_name = current_user.full_name or "A member"
            group_name = group.name if group else "the group"
            currency = group.currency if group and group.currency else "UGX"
            notify_all_group_members_sync(
                group_id=resolved_group_id,
                sender_id=str(current_user.id),
                title=f"💰 {member_name} just deposited",
                body=f"{member_name} deposited {currency} {int(pay_amount):,} in '{group_name}'.",
                data={
                    "type": "DEPOSIT_BROADCAST",
                    "group_id": resolved_group_id,
                    "transaction_id": str(ledger_entry.id),
                    "dedupe_key": f"group_deposit:{ledger_entry.id}",
                    "actor_id": str(current_user.id),
                },
                include_sender_in_inbox=True,
            )

        result = {
            "id": str(obligation.id),
            "obligation_id": str(obligation.id),
            "group_id": resolved_group_id,
            "status": obligation.status,
            "amountPaid": int(obligation.amount_paid),
            "amount_paid": int(obligation.amount_paid),
            "amountDue": int(obligation.amount_due),
            "amount_due": int(obligation.amount_due),
            "updatedAt": int(obligation.updated_at or now_ms),
            "updated_at": int(obligation.updated_at or now_ms),
        }
        return {**result, "data": result}

    # Fallback: Association Dues group payment without a pre-existing MemberObligation row
    assoc_config = None
    assoc_settings = None
    if group_id:
        assoc_config = session.exec(
            select(AssociationDuesConfig).where(AssociationDuesConfig.group_id == str(group_id))
        ).first()
        assoc_settings = session.exec(
            select(AssociationDuesOperationalSettings).where(
                AssociationDuesOperationalSettings.group_id == str(group_id)
            )
        ).first()
    else:
        user_memberships = session.exec(
            select(GroupMembership).where(GroupMembership.user_id == current_user.id)
        ).all()
        for m in user_memberships:
            cfg = session.exec(
                select(AssociationDuesConfig).where(AssociationDuesConfig.group_id == m.group_id)
            ).first()
            if cfg:
                group_id = m.group_id
                assoc_config = cfg
                assoc_settings = session.exec(
                    select(AssociationDuesOperationalSettings).where(
                        AssociationDuesOperationalSettings.group_id == m.group_id
                    )
                ).first()
                break

    if assoc_config and assoc_settings and group_id:
        dues_unit = int(assoc_config.dues_amount or 0)
        total_amount = int(amount_raw) if (amount_raw is not None and int(amount_raw) > 0) else (cycles_count * dues_unit)
        assoc_settings.total_collected = int(assoc_settings.total_collected or 0) + total_amount
        assoc_settings.current_balance = int(assoc_settings.current_balance or 0) + total_amount
        assoc_settings.updated_at = now_ms
        session.add(assoc_settings)
        session.commit()

        result = {
            "id": str(ob_id_raw or group_id),
            "obligation_id": str(ob_id_raw or group_id),
            "group_id": str(group_id),
            "status": "PAID",
            "amountPaid": total_amount,
            "amount_paid": total_amount,
            "updatedAt": now_ms,
            "updated_at": now_ms,
        }
        return {**result, "data": result}

    if ob_id_raw is not None:
        paid_val = int(float(amount_raw)) if (amount_raw is not None and float(amount_raw) > 0) else 0
        result = {
            "id": str(ob_id_raw),
            "obligation_id": str(ob_id_raw),
            "status": "PAID",
            "amountPaid": paid_val,
            "amount_paid": paid_val,
            "updatedAt": now_ms,
            "updated_at": now_ms,
        }
        return {**result, "data": result}

    raise HTTPException(status_code=404, detail="Obligation not found.")


@router.post("/pay", summary="Pay Association Dues or Queued Obligation")
def pay_association_dues_direct(
    payload: Any = Body(default=None),
    obligationId: Optional[str] = Query(default=None),
    obligation_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    body_dict = _parse_body_dict(payload)
    resolved_ob_id = obligation_id or obligationId or body_dict.get("obligation_id") or body_dict.get("obligationId")
    return execute_obligation_payment(
        session=session,
        current_user=current_user,
        obligation_id=str(resolved_ob_id) if resolved_ob_id is not None else None,
        body_data=body_dict,
    )


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
        background_tasks=background_tasks,
        include_sender_in_inbox=True,
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
