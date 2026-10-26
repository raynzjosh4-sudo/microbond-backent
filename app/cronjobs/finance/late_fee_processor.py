import logging
import asyncio
from datetime import datetime, timezone
from sqlmodel import Session, select

from app.core.database import engine
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupFinancialSettings
from app.models.group.finance import MemberObligation, GroupPenalty
from app.models.user.user import User
from app.models.user.security_email import UserSecurityEmail
from app.communications.sms_service import send_overdue_reminder_sms

logger = logging.getLogger(__name__)


def _try_send_overdue_notifications(session: Session, obligation: MemberObligation, penalty_amount: int = 0):
    """
    Notification chain for an obligation that missed deadline / entered grace period or turned LATE (Events 12, 13, 14):
    1. Group Chat System Event notice.
    2. Defaulter FCM push notification (Late Fee Applied).
    3. Defaulter Carrier SMS (if opted-in).
    4. Guarantor FCM Push & SMS alerts.
    """
    try:
        import uuid
        from app.models.group.chat import GroupChatMessage
        from app.core.firebase_config import send_push_notification
        from app.services.communication.sms.helpers.send_sms import send_sms
        from app.models.group.finance.guarantor_pledge import GuarantorPledge

        # Load dependencies
        group = session.exec(select(Group).where(Group.group_id == obligation.group_id)).first()
        user = session.exec(select(User).where(User.id == obligation.user_id)).first()
        fin_settings = session.exec(
            select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == obligation.group_id)
        ).first()
        membership = session.exec(
            select(GroupMembership).where(
                GroupMembership.group_id == obligation.group_id,
                GroupMembership.user_id == obligation.user_id
            )
        ).first()

        if not group or not user or not fin_settings or not membership:
            return

        member_name = user.full_name or "Member"
        group_name = group.name
        currency = group.currency or "UGX"
        unpaid = max(0, obligation.amount_due - obligation.amount_paid)
        total_outstanding = unpaid + penalty_amount

        # ── Event 13: Chat Notice in Group Thread ────────────────────────────
        chat_msg = GroupChatMessage(
            client_message_id=str(uuid.uuid4()),
            group_id=obligation.group_id,
            sender_id="SYSTEM",
            message_type="SYSTEM_EVENT",
            message_text=f"System notice: {member_name} missed the grace period deadline. A {penalty_amount:,} {currency} late fee has been attached to their account.",
            status="SENT"
        )
        session.add(chat_msg)
        session.commit()

        # ── Event 13: Push Notification to Defaulter ─────────────────────────
        if user.fcm_token:
            send_push_notification(
                token=user.fcm_token,
                title="❌ Late Fee Applied",
                body=f"Grace period expired. A {penalty_amount:,} {currency} penalty has been added. Total outstanding: {total_outstanding:,} {currency}.",
                data={"route": "deposit_screen", "group_id": group.group_id, "obligation_id": str(obligation.id)}
            )

        # ── Event 13: Carrier SMS to Defaulter (if opted in) ─────────────────
        if membership.sms_reminders_opted_in and user.phone_number:
            try:
                send_sms(
                    user.phone_number,
                    f"Microbond Notice: {penalty_amount:,} {currency} late fee applied for {group_name}. Total outstanding: {total_outstanding:,} {currency}."
                )
            except Exception as sms_err:
                logger.warning(f"[OVERDUE SMS] Failed: {sms_err}")

        # ── Event 14: Guarantor Liability Invocation ─────────────────────────
        pledges = session.exec(
            select(GuarantorPledge).where(
                GuarantorPledge.group_id == obligation.group_id,
                GuarantorPledge.borrower_user_id == obligation.user_id,
                GuarantorPledge.status == "ACTIVE"
            )
        ).all()

        for pledge in pledges:
            guarantor = session.get(User, pledge.guarantor_user_id)
            if not guarantor:
                continue

            if guarantor.fcm_token:
                send_push_notification(
                    token=guarantor.fcm_token,
                    title="⚠️ Guarantor Pledge Invoked",
                    body=f"{member_name} defaulted on {unpaid:,} {currency} in {group_name}. Your guarantor pledge is being charged to protect the group pot.",
                    data={"route": "guarantor_pledge_screen", "group_id": group.group_id}
                )

            if guarantor.phone_number:
                try:
                    send_sms(
                        guarantor.phone_number,
                        f"Microbond Default Notice: {member_name} defaulted on {unpaid:,} {currency}. As guarantor, please authorize collection to maintain group standing."
                    )
                except Exception as g_err:
                    logger.warning(f"[GUARANTOR SMS] Failed: {g_err}")

    except Exception as e:
        logger.error(f"[OVERDUE NOTIFY] Error sending notifications for obligation {obligation.id}: {e}")


def process_daily_late_fees():
    current_time_epoch = int(datetime.now(timezone.utc).timestamp() * 1000)

    with Session(engine) as session:
        # Phase 1: Fetch IDs only, no locks yet
        overdue_ids = session.exec(
            select(MemberObligation.id).where(
                MemberObligation.status.in_(["PENDING", "LATE"]),
                MemberObligation.due_date < current_time_epoch
            )
        ).all()

    for ob_id in overdue_ids:
        # Phase 2: Process each obligation in its own atomic transaction
        try:
            with Session(engine) as session:
                # Lock exactly this row using SKIP LOCKED
                obligation = session.exec(
                    select(MemberObligation)
                    .where(MemberObligation.id == ob_id)
                    .with_for_update(skip_locked=True)
                ).first()

                if not obligation or obligation.status not in ["PENDING", "LATE"]:
                    continue

                settings = session.exec(
                    select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == obligation.group_id)
                ).first()
                if not settings:
                    continue

                grace_ms = (settings.grace_period_hours * 3600000) if settings.enable_grace_period else 0
                cutoff_time = obligation.due_date + grace_ms
                default_cutoff_time = cutoff_time + (48 * 3600000)

                just_went_late = False
                penalty_val = settings.late_fee_amount if settings.enable_late_fees else 0

                # Event 12: Cutoff passed, grace period active alert (tier 0)
                if obligation.status == "PENDING" and obligation.due_date < current_time_epoch <= cutoff_time:
                    if obligation.last_reminder_tier != 0:
                        user = session.get(User, obligation.user_id)
                        group = session.get(Group, obligation.group_id)
                        unpaid = max(0, obligation.amount_due - obligation.amount_paid)
                        curr = group.currency or "UGX" if group else "UGX"
                        if user and user.fcm_token:
                            from app.core.firebase_config import send_push_notification
                            send_push_notification(
                                token=user.fcm_token,
                                title="⚠️ Payment Deadline Missed (Grace Period Active)",
                                body=f"Your Cycle {obligation.cycle_number} contribution has an unpaid balance of {unpaid:,} {curr}. Grace period active.",
                                data={"route": "deposit_screen", "group_id": obligation.group_id, "obligation_id": str(obligation.id)}
                            )
                        membership = session.exec(
                            select(GroupMembership).where(
                                GroupMembership.group_id == obligation.group_id,
                                GroupMembership.user_id == obligation.user_id
                            )
                        ).first()
                        if membership and getattr(membership, "sms_reminders_opted_in", False) and user and user.phone_number:
                            from app.services.communication.sms.helpers.send_sms import send_sms
                            try:
                                send_sms(
                                    user.phone_number,
                                    f"URGENT: Your {unpaid:,} {curr} balance for {group.name if group else 'Group'} is overdue. Pay within grace period to avoid late penalty."
                                )
                            except Exception as sms_err:
                                logger.warning(f"[GRACE PERIOD SMS] Failed: {sms_err}")
                        obligation.last_reminder_tier = 0
                        session.add(obligation)

                elif obligation.status == "PENDING" and current_time_epoch > cutoff_time:
                    obligation.status = "LATE"
                    just_went_late = True
                    logger.info(f"Obligation {obligation.id} marked LATE.")

                elif obligation.status == "LATE" and current_time_epoch > default_cutoff_time:
                    obligation.status = "DEFAULTED"
                    logger.info(f"Obligation {obligation.id} escalated to DEFAULTED.")

                session.add(obligation)

                # Apply Penalty logic if late fees are enabled
                if settings.enable_late_fees and obligation.status in ["LATE", "DEFAULTED"]:
                    twenty_four_hours_ago = current_time_epoch - (24 * 3600000)
                    recent_penalty = session.exec(
                        select(GroupPenalty).where(
                            GroupPenalty.obligation_id == obligation.id,
                            GroupPenalty.created_at >= twenty_four_hours_ago
                        )
                    ).first()

                    if not recent_penalty:
                        penalty = GroupPenalty(
                            group_id=obligation.group_id,
                            user_id=obligation.user_id,
                            obligation_id=obligation.id,
                            penalty_amount=settings.late_fee_amount,
                            reason=f"Late fee for missed payment on Obligation {obligation.id}"
                        )
                        session.add(penalty)

                # Commit immediately to release the row lock fast
                session.commit()

                # Send overdue notifications outside the lock window
                if just_went_late:
                    _try_send_overdue_notifications(session, obligation, penalty_amount=penalty_val)

        except Exception as e:
            logger.error(f"Error processing obligation {ob_id}: {str(e)}")

