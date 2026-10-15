import logging
from sqlmodel import Session, select
from app.models.group.group import Group
from app.models.group.finance import GroupPayout
from app.models.group.wallet import GroupWallet
from app.models.group.ledger import LedgerEntry
from app.models.user.user import User
from app.services.group.payout_hold_service import check_payout_holds
from app.services.group.payout_destination_resolver import resolve_member_payout_destination, mask_account_number
from app.services.mobile_money.disbursement_service import DisbursementService
from app.core.firebase_config import send_push_notification
from .dispatch_payout_notifications import dispatch_payout_notifications

logger = logging.getLogger(__name__)


def process_single_payout(session: Session, payout: GroupPayout, now_ms: int):
    # Fetch User and Group
    user = session.exec(select(User).where(User.id == payout.user_id)).first()
    group = session.exec(select(Group).where(Group.group_id == payout.group_id)).first()

    if not user or not group:
        logger.error(f"[PAYOUT_WORKER] User {payout.user_id} or Group {payout.group_id} not found for payout {payout.id}")
        payout.status = "FAILED"
        payout.hold_reason = "Recipient user or group entity does not exist."
        session.commit()
        return

    # ── 1. Check Payout Holds (Unpaid Obligations / Abuse Reports) ───────────
    is_held, hold_reason = check_payout_holds(session, payout.group_id, payout.user_id)
    if is_held:
        logger.warning(f"[PAYOUT_WORKER] Payout {payout.id} placed ON_HOLD: {hold_reason}")
        payout.status = "ON_HOLD"
        payout.hold_reason = hold_reason
        session.commit()

        if user.fcm_token:
            send_push_notification(
                token=user.fcm_token,
                title="⚠️ Payout on Hold",
                body=f"Your Round {payout.cycle_number} payout for {group.name} is on hold: {hold_reason}",
                data={"type": "PAYOUT_ON_HOLD", "group_id": payout.group_id, "payout_id": str(payout.id)}
            )
        return

    # ── 2. Check Security Cooldown (Device Swap Tripwire) ─────────────────────
    if user.security_cooldown_until and user.security_cooldown_until > now_ms:
        cooldown_msg = "Security cooldown active after recent device/SIM change."
        logger.warning(f"[PAYOUT_WORKER] Payout {payout.id} placed ON_HOLD: {cooldown_msg}")
        payout.status = "ON_HOLD"
        payout.hold_reason = cooldown_msg
        session.commit()
        return

    # ── 3. Check Group Pooled Balance (Strict Row Lock) ──────────────────────
    wallet = session.exec(
        select(GroupWallet)
        .where(GroupWallet.group_id == payout.group_id)
        .with_for_update()
    ).first()

    if not wallet or wallet.pooled_funds < payout.amount_expected:
        available = wallet.pooled_funds if wallet else 0
        logger.warning(
            f"[PAYOUT_WORKER] Insufficient funds in group {payout.group_id} wallet "
            f"(Pooled: {available:,} UGX, Needed: {payout.amount_expected:,} UGX). Delaying payout {payout.id}."
        )
        # Revert status to PENDING so next worker iteration can retry once remaining deposits settle
        payout.status = "PENDING"
        session.add(payout)
        session.commit()
        return

    # ── 4. Resolve Chosen Payout Destination Account ─────────────────────────
    chosen_account = resolve_member_payout_destination(session, payout.group_id, payout.user_id)
    masked_acc = mask_account_number(chosen_account.account_number)

    logger.info(
        f"[PAYOUT_WORKER] Processing payout {payout.id} -> User: {user.phone_number}, "
        f"Target: {chosen_account.provider_name} ({masked_acc}, source={chosen_account.source}), "
        f"Amount: {payout.amount_expected:,} UGX"
    )

    # ── 5. Execute B2C Mobile Money / Bank Disbursement ──────────────────────
    narrative = f"Payout Round {payout.cycle_number} - {group.name[:25]}"
    disbursement_result = DisbursementService.disburse(
        destination=chosen_account,
        amount=payout.amount_expected,
        narrative=narrative,
        external_id=f"payout_tx_{payout.id}_c{payout.cycle_number}"
    )

    if not disbursement_result.success:
        logger.error(f"[PAYOUT_WORKER] Disbursement failed for payout {payout.id}: {disbursement_result.error_message}")
        payout.status = "FAILED"
        payout.hold_reason = disbursement_result.error_message or "Disbursement gateway rejected transfer."
        session.commit()

        if user.fcm_token:
            send_push_notification(
                token=user.fcm_token,
                title="❌ Payout Failed",
                body=f"Failed to disburse your Round {payout.cycle_number} payout to {chosen_account.provider_name}. Please verify your payout destination.",
                data={"type": "PAYOUT_FAILED", "group_id": payout.group_id, "payout_id": str(payout.id)}
            )
        return

    # ── 6. Update Double-Entry Ledger & Wallet Balances ───────────────────────
    wallet.pooled_funds -= payout.amount_expected
    wallet.total_lifetime_payouts += payout.amount_expected
    wallet.updated_at = now_ms
    session.add(wallet)

    ledger_entry = LedgerEntry(
        group_id=payout.group_id,
        user_id=payout.user_id,
        payout_id=payout.id,
        source_account="GROUP_POOLED",
        destination_account=f"{chosen_account.provider_name}:{chosen_account.account_number}",
        amount=payout.amount_expected,
        currency="UGX",
        transaction_type="PAYOUT",
        external_reference_id=disbursement_result.transaction_id,
        status="SETTLED",
        settled_at=now_ms
    )
    session.add(ledger_entry)

    payout.status = "COMPLETED"
    payout.amount_received = payout.amount_expected
    session.add(payout)

    session.commit()

    logger.info(
        f"[PAYOUT_WORKER] Payout {payout.id} successfully COMPLETED! "
        f"Amount: {payout.amount_expected:,} UGX sent to {chosen_account.provider_name}."
    )

    # ── 7. Dispatch Multi-Channel Notifications ──────────────────────────────
    dispatch_payout_notifications(
        session=session,
        user=user,
        group=group,
        payout=payout,
        chosen_account=chosen_account,
        masked_acc=masked_acc
    )
