import logging
import uuid
from typing import Optional
from sqlmodel import Session, select

from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.wallet import GroupWallet
from app.models.group.ledger import LedgerEntry
from app.models.group.chat import GroupChatMessage
from app.models.user.user import User
from app.utils.time.now_epoch_ms import now_epoch_ms

logger = logging.getLogger(__name__)


def advance_cycle_and_apply_prepaid(
    session: Session,
    group_id: str,
    new_cycle: int,
    now_ms: Optional[int] = None
) -> int:
    """
    Advances the rotating group's active cycle to `new_cycle` and automatically
    draws down prepaid surplus savings (from `membership.credit_balance_ugx` and `wallet.prepaid_funds`)
    to satisfy dues for the newly active cycle.
    
    Returns the total number of members whose cycle dues were auto-satisfied.
    """
    if now_ms is None:
        now_ms = now_epoch_ms()

    # 1. Update rotating details current_cycle
    rotating = session.exec(
        select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
    ).first()

    if not rotating:
        logger.warning(f"[PREPAID_WATERFALL] Rotating details not found for group {group_id}")
        return 0

    rotating.current_cycle = new_cycle
    session.add(rotating)

    # 2. Fetch group wallet with pessimistic lock
    wallet = session.exec(
        select(GroupWallet).where(GroupWallet.group_id == group_id).with_for_update()
    ).first()

    # 3. Fetch active memberships with prepaid credit balances
    memberships_with_credit = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE",
            GroupMembership.credit_balance_ugx > 0
        )
    ).all()

    auto_satisfied_count = 0

    for membership in memberships_with_credit:
        credit = membership.credit_balance_ugx or 0
        if credit <= 0:
            continue

        # Find obligation for new cycle
        obligation = session.exec(
            select(MemberObligation).where(
                MemberObligation.group_id == group_id,
                MemberObligation.user_id == membership.user_id,
                MemberObligation.cycle_number == new_cycle
            )
        ).first()

        if not obligation or obligation.status == "PAID":
            continue

        needed = max(0, obligation.amount_due - obligation.amount_paid)
        if needed <= 0:
            continue

        draw_amount = min(credit, needed)
        if draw_amount <= 0:
            continue

        # Execute double-entry transfer: Prepaid -> Group Pooled
        membership.credit_balance_ugx -= draw_amount
        if wallet:
            wallet.prepaid_funds = max(0, (wallet.prepaid_funds or 0) - draw_amount)
            wallet.pooled_funds = (wallet.pooled_funds or 0) + draw_amount
            wallet.updated_at = now_ms
            session.add(wallet)

        obligation.amount_paid += draw_amount
        if obligation.amount_paid >= obligation.amount_due:
            obligation.status = "PAID"
            auto_satisfied_count += 1
        elif obligation.amount_paid > 0:
            obligation.status = "PARTIAL"
        obligation.updated_at = now_ms

        session.add(membership)
        session.add(obligation)

        # Ledger Entry for Audit Trail
        ledger = LedgerEntry(
            group_id=group_id,
            user_id=membership.user_id,
            source_account="MEMBER_PREPAID",
            destination_account="GROUP_POOLED",
            amount=draw_amount,
            currency="UGX",
            transaction_type="PREPAID_DRAWDOWN",
            external_reference_id=f"PREPAID-{new_cycle}-{uuid.uuid4().hex[:8].upper()}",
            status="SETTLED",
            settled_at=now_ms
        )
        session.add(ledger)

        # Chat Notification
        user = session.exec(select(User).where(User.id == membership.user_id)).first()
        user_name = user.full_name if user else "A member"
        
        chat_msg = GroupChatMessage(
            client_message_id=str(uuid.uuid4()),
            group_id=group_id,
            sender_id="SYSTEM",
            message_type="DEPOSIT",
            message_text=f"🔄 Auto-applied {draw_amount:,} UGX from {user_name}'s prepaid savings to Cycle {new_cycle} dues. (Remaining advance: {membership.credit_balance_ugx:,} UGX)",
            attachments=[{
                "cycle_number": new_cycle,
                "amount": draw_amount,
                "credit_remaining": membership.credit_balance_ugx,
                "obligation_status": obligation.status,
                "is_advance_deduction": True
            }],
            created_at=now_ms,
            updated_at=now_ms,
            status="SENT"
        )
        session.add(chat_msg)

        # Event 17: Push Notification to Advance Depositor
        if user and user.fcm_token:
            from app.core.firebase_config import send_push_notification
            try:
                send_push_notification(
                    token=user.fcm_token,
                    title=f"⚡ Auto-Payment Settled for Cycle {new_cycle}",
                    body=f"Your Cycle {new_cycle} contribution of {draw_amount:,} UGX was automatically collected from your prepaid balance. Remaining advance balance: {membership.credit_balance_ugx:,} UGX.",
                    data={"type": "PREPAID_AUTO_DEDUCTION", "group_id": group_id, "cycle_number": str(new_cycle)}
                )
            except Exception as push_err:
                logger.warning(f"[PREPAID_PUSH] Failed: {push_err}")

    session.commit()
    logger.info(
        f"[PREPAID_WATERFALL] Group {group_id} advanced to Cycle {new_cycle}. "
        f"Auto-applied prepaid savings for {auto_satisfied_count} member(s)."
    )
    return auto_satisfied_count
