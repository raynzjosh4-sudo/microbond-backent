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
    amount = payload.amount
    currency = group.currency or "UGX"
    payment_method = payload.payment_method or "TEST_WALLET"
    ref_id = payload.client_reference or f"DEP-{secrets.token_hex(6).upper()}"

    # 3. Determine cycle number & handle Rotating specifics
    current_cycle = 1
    base_due = amount
    if group.type == "MERRY_GO_ROUND":
        rot = session.exec(
            select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
        ).first()
        if rot:
            current_cycle = rot.current_cycle or 1
            base_due = int(rot.contribution_amount)

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

    obligation.amount_paid += amount
    if obligation.amount_paid >= obligation.amount_due:
        obligation.status = "PAID"
    elif obligation.amount_paid > 0:
        obligation.status = "PARTIAL"
    obligation.updated_at = now_ms
    session.add(obligation)

    # 5. Record double-entry LedgerEntry
    ledger_entry = LedgerEntry(
        group_id=group_id,
        user_id=current_user.id,
        obligation_id=obligation.id,
        source_account=payment_method,
        destination_account="GROUP_POOLED",
        amount=amount,
        transaction_type="DEPOSIT",
        external_reference_id=ref_id,
        status="SETTLED",
        settled_at=now_ms
    )
    session.add(ledger_entry)

    # 6. Update GroupWallet
    wallet = session.exec(
        select(GroupWallet).where(GroupWallet.group_id == group_id)
    ).first()
    if not wallet:
        wallet = GroupWallet(group_id=group_id, pooled_funds=0.0, reserve_funds=0.0)
        session.add(wallet)
        session.flush()

    wallet.pooled_funds = (wallet.pooled_funds or 0.0) + amount
    wallet.updated_at = now_ms
    session.add(wallet)

    # 7. Update Group total balance and Member total contributed
    group.total_balance = (group.total_balance or 0) + amount
    group.updated_at = now_ms
    session.add(group)

    membership.total_contributed = (membership.total_contributed or 0) + amount
    session.add(membership)

    # 8. Insert a DEPOSIT chat message into group thread
    depositor_name = current_user.full_name or "A member"
    deposit_msg = GroupChatMessage(
        client_message_id=str(uuid.uuid4()),
        group_id=group_id,
        sender_id=str(current_user.id),
        message_type="DEPOSIT",
        message_text=f"{depositor_name} deposited {amount:,} {currency}",
        attachments=[{
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method,
            "reference_id": ref_id,
            "cycle_number": current_cycle,
            "obligation_status": obligation.status,
            "is_verified": True
        }],
        created_at=now_ms
    )
    session.add(deposit_msg)

    # Commit the transaction atomically
    session.commit()
    session.refresh(ledger_entry)
    session.refresh(group)
    session.refresh(membership)
    session.refresh(obligation)

    # 9. Real-time WebSocket Ring Status Broadcast
    try:
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
        session=session
    )

    # Calculate group ring completion fraction
    from app.services.group.dashboard_summary_service import GroupDashboardSummaryService
    ring = GroupDashboardSummaryService.calculate_group_ring(session, group_id)
    fraction = ring.ring_fraction if hasattr(ring, "ring_fraction") else 0.0

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
        timestamp=now_ms
    )
