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


def _try_send_overdue_notifications(session: Session, obligation: MemberObligation):
    """
    Notification chain for an obligation that just turned LATE:
    1. Email first — if the member has a verified security email.
    2. SMS after — if the group admin enabled SMS reminders AND the member opted in.
    """
    try:
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

        # Skip if group doesn't have SMS/call reminders enabled
        if not fin_settings.enable_sms_call_reminders:
            return

        member_name = user.full_name or "Member"
        group_name = group.name
        currency = group.currency

        # ── 1. Email first (if member opted in and has verified security email) ─
        security_email_row = session.exec(
            select(UserSecurityEmail).where(
                UserSecurityEmail.user_id == obligation.user_id,
                UserSecurityEmail.is_verified == True
            )
        ).first()

        if security_email_row and membership.email_reminders_opted_in:
            try:
                from app.services.communication.email_service import EmailNotificationService
                from app.services.communication.email_templates import build_overdue_reminder_email

                subject = f"⚠️ Overdue Payment — {group_name}"
                html_body = build_overdue_reminder_email(
                    member_name=member_name,
                    group_name=group_name,
                    amount_due=obligation.amount_due,
                    currency=currency
                )
                asyncio.run(EmailNotificationService._dispatch(
                    recipient_email=security_email_row.email,
                    subject=subject,
                    html_body=html_body
                ))
                logger.info(f"[OVERDUE EMAIL] Sent to {security_email_row.email} for obligation {obligation.id}")
            except Exception as email_err:
                logger.warning(f"[OVERDUE EMAIL] Failed for obligation {obligation.id}: {email_err}")

        # ── 2. SMS after (only if member opted in to SMS for this group) ──────
        if membership.sms_reminders_opted_in and user.phone_number:
            sent = send_overdue_reminder_sms(
                phone_number=user.phone_number,
                member_name=member_name,
                group_name=group_name,
                amount_due=obligation.amount_due,
                currency=currency
            )
            if sent:
                logger.info(f"[OVERDUE SMS] Sent to {user.phone_number} for obligation {obligation.id}")

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
                if obligation.status == "PENDING" and current_time_epoch > cutoff_time:
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
                    _try_send_overdue_notifications(session, obligation)

        except Exception as e:
            logger.error(f"Error processing obligation {ob_id}: {str(e)}")

