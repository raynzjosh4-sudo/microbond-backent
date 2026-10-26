import uuid
import time
import secrets
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.finance import MemberObligation
from app.models.group.wallet import GroupWallet
from app.models.group.ledger import LedgerEntry
from app.models.group.chat import GroupChatMessage
from app.utils.time.now_epoch_ms import now_epoch_ms
from app.services.finance.ledger.broadcast_group_ring_update import broadcast_group_ring_update
from app.services.websocket_manager import ws_manager
from app.api.routes.group.chat.messages.helpers.messages_helpers import broadcast_system_message_sync
from .schemas import DirectDepositRequest, DirectDepositResponse
from .helpers.trigger_post_deposit_notifications import trigger_post_deposit_notifications


logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/{group_id}/deposits/direct",
    response_model=DirectDepositResponse,
    summary="Record Direct / Peer-to-Peer Group Deposit",
    description="Direct deposit endpoint for rotating (and other) groups. Immediately updates ledger, member obligations, group wallet, countdowns, statistics, and injects a deposit message into the group thread."
)
@router.post(
    "/{group_id}/deposit",
    response_model=DirectDepositResponse,
    summary="Record Group Deposit (Alias)"
)
async def direct_deposit(
    group_id: str,
    payload: DirectDepositRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify User is an active member
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be an active member of this group to make deposits."
        )

    # 2. Fetch Group
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    now_ms = now_epoch_ms()

    # Rule 1: Group must not be forming
    if group.status in ["FORMING", "PENDING"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Group is still forming ({group.member_count}/{group.max_members or '?'} members). Deposits open once the circle is full."
        )

    # 3. Determine cycle number & handle Rotating specifics
    rot = None
    current_cycle = 1
    base_due = payload.amount
    if group.type == "MERRY_GO_ROUND":
        rot = session.exec(
            select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
        ).first()
        if rot:
            if rot.group_start_time and now_ms < rot.group_start_time and not rot.is_payout_order_locked:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This group schedule has not started yet. No deposits can be accepted until the start time."
                )
            current_cycle = rot.current_cycle or 1
            base_due = int(rot.contribution_amount)

    amount = payload.amount
    currency = group.currency or "UGX"
    payment_method = payload.payment_method or "TEST_WALLET"
    ref_id = payload.client_reference or f"DEP-{secrets.token_hex(6).upper()}"

    # 4. Find or create the active MemberObligation
    obligation = session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == group_id,
            MemberObligation.user_id == current_user.id,
            MemberObligation.cycle_number == current_cycle
        )
    ).first()

    if not obligation:
        # Create an obligation row for tracking if this cycle was not yet pre-generated
        obligation = MemberObligation(
            group_id=group_id,
            user_id=current_user.id,
            cycle_number=current_cycle,
            amount_due=base_due,
            amount_paid=0,
            status="PENDING",
            due_date=now_ms + (7 * 86400000)
        )
        session.add(obligation)
        session.flush()

    # 4b. Surplus-Aware Deposit Split:
    # Cap current cycle at remaining due amount; route any surplus to member's prepaid credit balance
    needed_for_cycle = max(0, obligation.amount_due - obligation.amount_paid)
    if group.type == "MERRY_GO_ROUND":
        if amount <= needed_for_cycle:
            cycle_deposit = amount
            surplus = 0
        else:
            cycle_deposit = needed_for_cycle
            surplus = amount - needed_for_cycle
            if rot and not rot.allow_advance_deposits:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Advance deposits are disabled for this group. Maximum allowed deposit for this cycle is {needed_for_cycle:,} {currency}."
                )
    else:
        cycle_deposit = amount
        surplus = 0

    obligation.amount_paid += cycle_deposit
    if obligation.amount_paid >= obligation.amount_due:
        obligation.status = "PAID"
    elif obligation.amount_paid > 0:
        obligation.status = "PARTIAL"
    obligation.updated_at = now_ms
    session.add(obligation)

    # 5. Record double-entry LedgerEntry for cycle deposit
    ledger_entry = LedgerEntry(
        group_id=group_id,
        user_id=current_user.id,
        obligation_id=obligation.id,
        source_account=payment_method,
        destination_account="GROUP_POOLED",
        amount=cycle_deposit,
        transaction_type="DEPOSIT",
        external_reference_id=ref_id,
        status="SETTLED",
        settled_at=now_ms
    )
    session.add(ledger_entry)

    # If surplus exists, record prepaid savings credit ledger entry
    if surplus > 0:
        surplus_ledger = LedgerEntry(
            group_id=group_id,
            user_id=current_user.id,
            obligation_id=obligation.id,
            source_account=payment_method,
            destination_account="MEMBER_PREPAID_CREDIT",
            amount=surplus,
            transaction_type="PREPAID_SAVINGS_CREDIT",
            external_reference_id=f"{ref_id}-PREPAID",
            status="SETTLED",
            settled_at=now_ms
        )
        session.add(surplus_ledger)

    # 6. Update GroupWallet: pooled_funds only gets cycle_deposit; prepaid_funds gets surplus
    wallet = session.exec(
        select(GroupWallet).where(GroupWallet.group_id == group_id)
    ).first()
    if not wallet:
        wallet = GroupWallet(group_id=group_id, pooled_funds=0, prepaid_funds=0, reserve_funds=0)
        session.add(wallet)
        session.flush()

    wallet.pooled_funds = (wallet.pooled_funds or 0) + cycle_deposit
    if surplus > 0:
        wallet.prepaid_funds = (wallet.prepaid_funds or 0) + surplus
    wallet.updated_at = now_ms
    session.add(wallet)

    # 7. Update Group total balance and Member total contributed & prepaid credit balance
    group.total_balance = (group.total_balance or 0) + amount
    group.updated_at = now_ms
    session.add(group)

    membership.total_contributed = (membership.total_contributed or 0) + amount
    if surplus > 0:
        membership.credit_balance_ugx = (membership.credit_balance_ugx or 0) + surplus
    session.add(membership)

    # 8. Announce verified deposit into group thread via System Event Message
    depositor_name = current_user.full_name or "A member"
    remaining_due = max(0, obligation.amount_due - obligation.amount_paid)
    if surplus > 0:
        msg_text = (
            f"💰 Verified Deposit: {depositor_name} deposited {amount:,} {currency}! "
            f"{cycle_deposit:,} {currency} settled for Cycle {current_cycle} obligation, and "
            f"{surplus:,} {currency} credited as advance surplus for future cycles 🌟"
        )
    elif obligation.status == "PARTIAL":
        msg_text = (
            f"💰 Partial Deposit: {depositor_name} deposited {amount:,} {currency} for Cycle {current_cycle}. "
            f"Remaining due: {remaining_due:,} {currency}."
        )
    else:
        msg_text = (
            f"💰 Verified Deposit: {depositor_name} deposited {amount:,} {currency} for Cycle {current_cycle} "
            f"(Settled in Full). Remaining due: 0 {currency}."
        )

    receipt_attachment = {
        "category": "DEPOSIT_NOTICE",
        "amount": amount,
        "currency": currency,
        "payment_method": payment_method,
        "reference_id": ref_id,
        "cycle_number": current_cycle,
        "cycle_contribution": cycle_deposit,
        "surplus_advance": surplus,
        "remaining_due": remaining_due,
        "obligation_status": obligation.status,
        "depositor_id": str(current_user.id),
        "depositor_name": depositor_name,
        "is_verified": True
    }

    # Commit the transaction atomically
    session.commit()
    session.refresh(ledger_entry)
    session.refresh(group)
    session.refresh(membership)
    session.refresh(obligation)

    # 9. Broadcast system event message into group chat (saves to DB & triggers push/websockets)
    system_msg = broadcast_system_message_sync(
        group_id=group_id,
        message_text=msg_text,
        message_type="SYSTEM_EVENT",
        sender_id="SYSTEM",
        session=session,
        background_tasks=background_tasks,
        attachments=[receipt_attachment]
    )

    # 10. Real-time WebSocket Broadcasts (Chat & Ring Status)
    try:
        if system_msg:
            await ws_manager.broadcast_to_group(
                group_id,
                {
                    "event_type": "NEW_MESSAGE",
                    "message": system_msg.model_dump(mode="json")
                }
            )
        await broadcast_group_ring_update(
            group_id=group_id,
            depositor_name=depositor_name,
            amount=amount
        )
    except Exception as ws_err:
        logger.warning(f"[DIRECT_DEPOSIT] WebSocket broadcast warning: {ws_err}")

    # 10. Post-deposit notification tasks (Push & SMS receipts)
    trigger_post_deposit_notifications(
        group_id=group_id,
        user_id=current_user.id,
        amount_deposited=amount,
        session=session,
        cycle_deposit=cycle_deposit,
        surplus=surplus,
        obligation_status=obligation.status,
        remaining_due=remaining_due,
        cycle_number=current_cycle,
        ref_id=ref_id
    )

    # Calculate group ring completion fraction
    from app.services.group.dashboard_summary_service import GroupDashboardSummaryService
    try:
        ring = GroupDashboardSummaryService.calculate_group_ring(session, group_id)
        fraction = ring.ring_fraction if hasattr(ring, "ring_fraction") else 0.0
    except Exception as ring_err:
        logger.warning(f"[DIRECT_DEPOSIT] Ring calculation warning: {ring_err}")
        fraction = 0.0

    return DirectDepositResponse(
        status="SUCCESS",
        message=f"Deposit of {amount:,} {currency} successfully recorded.",
        transaction_id=str(ledger_entry.id),
        reference_id=ref_id,
        group_id=group_id,
        amount_deposited=amount,
        member_total_contributed=membership.total_contributed,
        cycle_number=current_cycle,
        obligation_status=obligation.status,
        group_total_balance=group.total_balance,
        ring_completion_fraction=fraction,
        timestamp=now_ms,
        cycle_contribution_credited=cycle_deposit,
        advance_savings_credited=surplus,
        member_prepaid_balance=membership.credit_balance_ugx
    )
