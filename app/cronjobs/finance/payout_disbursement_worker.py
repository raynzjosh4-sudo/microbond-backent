import logging
import time
import asyncio
from typing import Optional
from sqlmodel import Session, select

from app.core.database import engine
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import GroupPayout
from app.models.group.wallet import GroupWallet
from app.models.group.ledger import LedgerEntry
from app.models.user.user import User
from app.models.user.security_email import UserSecurityEmail
from app.services.group.payout_hold_service import check_payout_holds
from app.services.group.payout_destination_resolver import (
    resolve_member_payout_destination,
    mask_account_number,
    ResolvedPayoutAccount
)
from app.services.mobile_money.disbursement_service import DisbursementService
from app.core.firebase_config import send_push_notification
from app.services.push_notifications import notify_all_group_members
from app.communications.sms_service import send_payout_disbursed_sms
from app.services.communication.email_service import EmailNotificationService
from app.services.communication.email_templates import build_payout_disbursed_email

logger = logging.getLogger(__name__)


def process_due_group_payouts():
    """
    Background worker that runs periodically on APScheduler.
    Finds all matured group payouts due for disbursement, verifies group rules
    and financial liquidity, resolves each member's chosen destination account,
    and executes telecom B2C payout disbursements.
    """
    logger.info("[PAYOUT_WORKER] Checking for due group payouts...")
    now_ms = int(time.time() * 1000)

    with Session(engine) as session:
        # 1. Query pending payouts whose scheduled payout date has arrived
        due_payouts = session.exec(
            select(GroupPayout)
            .where(
                GroupPayout.status == "PENDING",
                GroupPayout.payout_date <= now_ms
            )
            .order_by(GroupPayout.payout_date.asc())
        ).all()

        if not due_payouts:
            logger.info("[PAYOUT_WORKER] No due payouts found.")
            return

        logger.info(f"[PAYOUT_WORKER] Found {len(due_payouts)} pending payout(s) ready for disbursement.")

        for payout in due_payouts:
            try:
                _process_single_payout(session, payout, now_ms)
            except Exception as e:
                logger.exception(f"[PAYOUT_WORKER] Unhandled error processing payout ID {payout.id}: {e}")
                session.rollback()


def _process_single_payout(session: Session, payout: GroupPayout, now_ms: int):
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
        # Keep PENDING so next cron iteration can re-evaluate after remaining deposits settle
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
    payout.status = "PROCESSING"
    session.add(payout)
    session.flush()

    narrative = f"Payout Round {payout.cycle_number} - {group.name[:25]}"
    disbursement_result = DisbursementService.disburse(
        destination=chosen_account,
        amount=payout.amount_expected,
        narrative=narrative,
        external_id=f"payout_tx_{payout.id}_{now_ms}"
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
    _dispatch_payout_notifications(
        session=session,
        user=user,
        group=group,
        payout=payout,
        chosen_account=chosen_account,
        masked_acc=masked_acc
    )


def _dispatch_payout_notifications(
    session: Session,
    user: User,
    group: Group,
    payout: GroupPayout,
    chosen_account: ResolvedPayoutAccount,
    masked_acc: str
):
    member_name = user.full_name or "Member"
    amount_str = f"{payout.amount_expected:,} UGX"

    # A. Push Notification to Recipient
    if user.fcm_token:
        try:
            send_push_notification(
                token=user.fcm_token,
                title="💰 Payout Received!",
                body=f"Your payout of {amount_str} for {group.name} (Round {payout.cycle_number}) has been sent to {chosen_account.provider_name} ({masked_acc}).",
                data={
                    "type": "PAYOUT_COMPLETED",
                    "group_id": payout.group_id,
                    "payout_id": str(payout.id),
                    "amount": str(payout.amount_expected)
                }
            )
        except Exception as ex:
            logger.warning(f"[PAYOUT_NOTIF] FCM recipient push failed: {ex}")

    # B. Push Notification to Group Members
    try:
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        coro = notify_all_group_members(
            group_id=payout.group_id,
            sender_id=str(user.id),
            title=f"🎉 {group.name} Payout Complete",
            body=f"{member_name} received their Round {payout.cycle_number} payout of {amount_str}!",
            data={
                "type": "GROUP_PAYOUT_EVENT",
                "group_id": payout.group_id,
                "cycle_number": str(payout.cycle_number)
            }
        )

        if loop and loop.is_running():
            asyncio.create_task(coro)
        else:
            asyncio.run(coro)
    except Exception as ex:
        logger.warning(f"[PAYOUT_NOTIF] Group broadcast push failed: {ex}")

    # C. SMS Notification (Africa's Talking)
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == payout.group_id,
            GroupMembership.user_id == user.id
        )
    ).first()

    if membership and membership.sms_reminders_opted_in and user.phone_number:
        try:
            send_payout_disbursed_sms(
                phone_number=user.phone_number,
                member_name=member_name,
                group_name=group.name,
                amount_paid=payout.amount_expected,
                provider_name=chosen_account.provider_name,
                masked_account=masked_acc,
                currency="UGX"
            )
        except Exception as ex:
            logger.warning(f"[PAYOUT_NOTIF] SMS alert failed: {ex}")

    # D. Verified Security Email (Resend)
    security_email = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.user_id == user.id,
            UserSecurityEmail.is_verified == True
        )
    ).first()

    if security_email and security_email.email:
        try:
            html_body = build_payout_disbursed_email(
                member_name=member_name,
                group_name=group.name,
                amount_paid=payout.amount_expected,
                cycle_number=payout.cycle_number,
                provider_name=chosen_account.provider_name,
                masked_account=masked_acc,
                currency="UGX"
            )
            EmailNotificationService.send_email(
                to_email=security_email.email,
                subject=f"Payout Disbursed ({amount_str}) — {group.name}",
                html_content=html_body
            )
        except Exception as ex:
            logger.warning(f"[PAYOUT_NOTIF] Email alert failed: {ex}")
