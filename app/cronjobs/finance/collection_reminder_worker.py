import logging
from sqlmodel import Session, select
from datetime import datetime, timezone

from app.core.database import engine
from app.models.group.group import Group
from app.models.group.finance import MemberObligation
from app.models.group.rotating import RotatingGroupDetails
from app.models.user.user import User
from app.core.firebase_config import send_push_notification
from app.utils.time.now_epoch_ms import now_epoch_ms

logger = logging.getLogger(__name__)


def process_collection_reminders():
    """
    Cron Job that checks upcoming pending and partial obligations across rotating groups and
    sends timely tiered reminders (48h and 24h) with FCM push and carrier SMS (if opted-in).
    """
    now_ms = now_epoch_ms()

    try:
        with Session(engine) as session:
            # Query active rotating groups
            groups = session.exec(
                select(Group, RotatingGroupDetails)
                .join(RotatingGroupDetails, Group.group_id == RotatingGroupDetails.group_id)
                .where(Group.status == "ACTIVE")
            ).all()

            for group, rotating in groups:
                currency = group.currency or "UGX"

                # Find obligations due within next 48 hours that are unpaid
                upcoming_obligations = session.exec(
                    select(MemberObligation)
                    .where(
                        MemberObligation.group_id == group.group_id,
                        MemberObligation.status.in_(["PENDING", "PARTIAL"]),
                        MemberObligation.amount_paid < MemberObligation.amount_due,
                        MemberObligation.due_date > now_ms,
                        MemberObligation.due_date <= now_ms + (48 * 3600 * 1000)
                    )
                ).all()

                for ob in upcoming_obligations:
                    user = session.get(User, ob.user_id)
                    if not user:
                        continue

                    from app.models.group.group import GroupMembership
                    from app.services.communication.sms.helpers.send_sms import send_sms

                    membership = session.exec(
                        select(GroupMembership).where(
                            GroupMembership.group_id == group.group_id,
                            GroupMembership.user_id == ob.user_id
                        )
                    ).first()

                    hours_left = max(1, int((ob.due_date - now_ms) / (3600 * 1000)))
                    remaining = ob.amount_due - ob.amount_paid

                    # Tier 1: 48h Reminder (between 24h and 48h)
                    if 24 < hours_left <= 48 and (ob.last_reminder_tier is None or ob.last_reminder_tier > 48):
                        if user.fcm_token:
                            send_push_notification(
                                token=user.fcm_token,
                                title="📅 Deposit Reminder (48h Remaining)",
                                body=f"Your contribution of {remaining:,} {currency} for {group.name} is due in ~{hours_left}h.",
                                data={
                                    "type": "DEPOSIT_REMINDER",
                                    "route": "deposit_screen",
                                    "group_id": group.group_id,
                                    "obligation_id": str(ob.id),
                                    "cycle_number": str(ob.cycle_number)
                                }
                            )
                        ob.last_reminder_tier = 48
                        ob.updated_at = now_ms
                        session.add(ob)
                        logger.info(f"[REMINDER_WORKER] Sent 48h reminder to {user.phone_number} for {group.name}.")

                    # Tier 2: 24h Reminder (<= 24h)
                    elif hours_left <= 24 and (ob.last_reminder_tier is None or ob.last_reminder_tier > 24):
                        if user.fcm_token:
                            send_push_notification(
                                token=user.fcm_token,
                                title="⏰ Deposit Reminder (24h Left)",
                                body=f"Friendly reminder: {remaining:,} {currency} contribution for {group.name} is due in ~{hours_left}h.",
                                data={
                                    "type": "DEPOSIT_REMINDER",
                                    "route": "deposit_screen",
                                    "group_id": group.group_id,
                                    "obligation_id": str(ob.id),
                                    "cycle_number": str(ob.cycle_number)
                                }
                            )

                        # Carrier SMS (Opted-in only)
                        if membership and getattr(membership, "sms_reminders_opted_in", False) and user.phone_number:
                            try:
                                send_sms(
                                    phone_number=user.phone_number,
                                    message=f"Microbond Reminder: Your {remaining:,} {currency} contribution for {group.name} is due tomorrow."
                                )
                                logger.info(f"[REMINDER_WORKER] Dispatched 24h SMS to {user.phone_number} for {group.name}.")
                            except Exception as sms_err:
                                logger.warning(f"[REMINDER_WORKER] Failed sending SMS: {sms_err}")

                        ob.last_reminder_tier = 24
                        ob.updated_at = now_ms
                        session.add(ob)
                        logger.info(f"[REMINDER_WORKER] Sent 24h reminder to {user.phone_number} for {group.name}.")

            session.commit()

    except Exception as e:
        logger.warning(f"[REMINDER_WORKER] Error processing collection reminders: {e}")
