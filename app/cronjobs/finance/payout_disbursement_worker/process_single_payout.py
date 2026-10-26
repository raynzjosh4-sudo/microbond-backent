import logging
from sqlmodel import Session, select
from app.models.group.group import Group, GroupMembership
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


def process_single_payout(session: Session, payout: GroupPayout, now_ms: int, force_disburse: bool = False):
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

    # ── 3b. Enforce Rotating Group Settings (Auto-Disburse & Multi-Sig) ───────
    from app.models.group.rotating import RotatingGroupDetails
    rotating = None
    if group.type == "MERRY_GO_ROUND":
        rotating = session.exec(
            select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == payout.group_id)
        ).first()

    if rotating and not force_disburse:
        # Check Multi-Sig requirement first
        if rotating.multi_sig_payout_approval and payout.status not in ["APPROVED_FOR_DISBURSEMENT", "APPROVED_BY_DECAY"]:
            payout.status = "PENDING_MULTISIG_APPROVAL"
            payout.hold_reason = "Awaiting required multi-signature approvals (Admin & Treasurer)."
            session.add(payout)
            session.commit()
            logger.info(f"[PAYOUT_WORKER] Payout {payout.id} held for Multi-Sig approval.")

            # Event 16: Multi-Sig Approval Requested Push to Signers
            try:
                signers = session.exec(
                    select(GroupMembership).where(
                        GroupMembership.group_id == payout.group_id,
                        GroupMembership.status == "ACTIVE",
                        GroupMembership.role.in_(["ADMIN", "TREASURER"])
                    )
                ).all()
                signer_uids = [s.user_id for s in signers]
                if signer_uids:
                    signer_users = session.exec(select(User).where(User.id.in_(signer_uids))).all()
                    for su in signer_users:
                        if su.fcm_token:
                            send_push_notification(
                                token=su.fcm_token,
                                title="✍️ Payout Signature Required",
                                body=f"Cycle {payout.cycle_number} pot ({payout.amount_expected:,} UGX) is ready. Please review and sign with your PIN.",
                                data={"route": "multisig_approval_screen", "payout_id": str(payout.id), "group_id": payout.group_id}
                            )
            except Exception as ms_err:
                logger.warning(f"[MULTISIG NOTIF] Failed: {ms_err}")

            return

        # Check Auto-Disburse requirement
        if not rotating.auto_disburse_when_full and payout.status != "APPROVED_FOR_DISBURSEMENT":
            payout.status = "READY_FOR_DISBURSEMENT"
            payout.hold_reason = "Awaiting manual disbursement release by Group Admin."
            session.add(payout)
            session.commit()
            logger.info(f"[PAYOUT_WORKER] Payout {payout.id} waiting for manual admin release.")
            return

    # ── 3c. Calculate Early-Turn Security Hold ───────────────────────────────
    hold_amount = 0
    disburse_amount = payout.amount_expected
    if rotating and rotating.early_turn_security_hold_percentage > 0:
        total_cycles = rotating.number_of_cycles or 10
        half_mark = (total_cycles + 1) // 2
        if payout.cycle_number <= half_mark:
            hold_pct = rotating.early_turn_security_hold_percentage / 100.0
            hold_amount = int(round(payout.amount_expected * hold_pct))
            disburse_amount = payout.amount_expected - hold_amount
            logger.info(
                f"[PAYOUT_WORKER] Applying early-turn security hold: {hold_amount:,} UGX "
                f"({rotating.early_turn_security_hold_percentage}%) for Round {payout.cycle_number}."
            )

    # ── 4. Resolve Chosen Payout Destination Account ─────────────────────────
    chosen_account = resolve_member_payout_destination(session, payout.group_id, payout.user_id)
    masked_acc = mask_account_number(chosen_account.account_number)

    logger.info(
        f"[PAYOUT_WORKER] Processing payout {payout.id} -> User: {user.phone_number}, "
        f"Target: {chosen_account.provider_name} ({masked_acc}, source={chosen_account.source}), "
        f"Amount: {disburse_amount:,} UGX (Gross: {payout.amount_expected:,} UGX)"
    )

    # ── 5. Execute B2C Mobile Money / Bank Disbursement ──────────────────────
    narrative = f"Payout Round {payout.cycle_number} - {group.name[:25]}"
    disbursement_result = DisbursementService.disburse(
        destination=chosen_account,
        amount=disburse_amount,
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
    wallet.total_lifetime_payouts += disburse_amount
    if hold_amount > 0:
        wallet.reserve_funds += hold_amount
    wallet.updated_at = now_ms
    session.add(wallet)

    ledger_entry = LedgerEntry(
        group_id=payout.group_id,
        user_id=payout.user_id,
        payout_id=payout.id,
        source_account="GROUP_POOLED",
        destination_account=f"{chosen_account.provider_name}:{chosen_account.account_number}",
        amount=disburse_amount,
        currency="UGX",
        transaction_type="PAYOUT",
        external_reference_id=disbursement_result.transaction_id,
        status="SETTLED",
        settled_at=now_ms
    )
    session.add(ledger_entry)

    payout.status = "COMPLETED"
    payout.amount_received = disburse_amount
    if hold_amount > 0:
        payout.hold_reason = f"Security reserve: {hold_amount:,} UGX held in escrow until cycle completion."
    session.add(payout)

    from app.services.audit_service import AuditService
    AuditService.record_event(
        session=session,
        action="PAYOUT_COMPLETED",
        entity_type="PAYOUT",
        entity_id=str(payout.id),
        payload={
            "group_id": payout.group_id,
            "user_id": str(payout.user_id),
            "amount_disbursed": disburse_amount,
            "amount_held": hold_amount,
            "cycle_number": payout.cycle_number,
            "transaction_id": disbursement_result.transaction_id,
            "provider": chosen_account.provider_name
        },
        actor_user_id=payout.user_id
    )

    # Event 15: Chat Celebration Banner
    from app.models.group.chat import GroupChatMessage
    import uuid
    curr = group.currency or "UGX"
    hold_str = f" ({hold_amount:,} {curr} retained in security escrow)" if hold_amount > 0 else ""
    payout_msg = GroupChatMessage(
        client_message_id=str(uuid.uuid4()),
        group_id=payout.group_id,
        sender_id="SYSTEM",
        message_type="PAYOUT_COMPLETED",
        message_text=f"🎉 Cycle {payout.cycle_number} Payout Disbursed! {user.full_name} has received {disburse_amount:,} {curr}{hold_str}.",
        attachments=[{
            "has_action_button": True,
            "action_text": "View Payout Receipt",
            "action_route": "payout_receipt_screen",
            "payout_id": str(payout.id),
            "amount": disburse_amount,
            "hold_amount": hold_amount
        }],
        created_at=now_ms,
        status="SENT"
    )
    session.add(payout_msg)

    session.commit()

    logger.info(
        f"[PAYOUT_WORKER] Payout {payout.id} successfully COMPLETED! "
        f"Amount: {disburse_amount:,} UGX sent to {chosen_account.provider_name}."
    )

    # ── 6b. Generate Cycle Milestone Report & Post Visual Report Card ─────────
    if rotating:
        try:
            from app.services.group.rotating.rotating_report_service import (
                generate_and_save_cycle_report,
                post_cycle_report_card_to_chat
            )
            cycle_report = generate_and_save_cycle_report(
                session=session,
                group_id=payout.group_id,
                cycle_number=payout.cycle_number,
                payout=payout
            )
            post_cycle_report_card_to_chat(session=session, report=cycle_report)
        except Exception as ex:
            logger.warning(f"[PAYOUT_WORKER] Failed generating rotating cycle report: {ex}")

    # ── 7. Check Cycle Completion & Auto-Renewal / Intermediate Cycle Advance ──
    if rotating and rotating.number_of_cycles:
        if payout.cycle_number >= rotating.number_of_cycles:
            # Check if all scheduled payouts in this cycle have COMPLETED
            uncompleted_payouts = session.exec(
                select(GroupPayout).where(
                    GroupPayout.group_id == payout.group_id,
                    GroupPayout.status != "COMPLETED"
                )
            ).all()

            if not uncompleted_payouts:
                if rotating.auto_renew_cycle:
                    from app.services.group.rotating.cycle_renewal_service import execute_cycle_renewal
                    logger.info(f"[PAYOUT_WORKER] All payouts complete for group {group.group_id}. Triggering Auto-Renewal.")
                    execute_cycle_renewal(session, payout.group_id, rotating, now_ms=now_ms)
                else:
                    group.status = "COMPLETED"
                    session.add(group)
                    session.commit()
                    logger.info(f"[PAYOUT_WORKER] Group {group.group_id} has reached completion of all cycles.")
        else:
            # Intermediate cycle completed: Advance to next cycle & auto-apply prepaid surplus
            next_cycle = payout.cycle_number + 1
            from app.services.group.rotating.prepaid_waterfall_service import advance_cycle_and_apply_prepaid
            logger.info(f"[PAYOUT_WORKER] Intermediate round {payout.cycle_number} complete. Advancing to Cycle {next_cycle}.")
            advance_cycle_and_apply_prepaid(session, payout.group_id, new_cycle=next_cycle, now_ms=now_ms)

    # ── 8. Dispatch Multi-Channel Notifications ──────────────────────────────
    dispatch_payout_notifications(
        session=session,
        user=user,
        group=group,
        payout=payout,
        chosen_account=chosen_account,
        masked_acc=masked_acc,
        hold_amount=hold_amount,
        disburse_amount=disburse_amount
    )

