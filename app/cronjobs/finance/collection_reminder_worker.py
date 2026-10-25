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
    Cron Job that checks upcoming pending obligations across rotating groups and
    sends timely reminders based on each group's customized reminder_lead_time_hours.
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
                lead_hours = rotating.reminder_lead_time_hours or 24
                lead_ms = lead_hours * 3600 * 1000

                # Find obligations due within this lead window
                upcoming_obligations = session.exec(
                    select(MemberObligation)
                    .where(
                        MemberObligation.group_id == group.group_id,
                        MemberObligation.status == "PENDING",
                        MemberObligation.due_date > now_ms,
                        MemberObligation.due_date <= now_ms + lead_ms
                    )
                ).all()

                for ob in upcoming_obligations:
                    user = session.get(User, ob.user_id)
                    if user and user.fcm_token:
                        hours_left = max(1, int((ob.due_date - now_ms) / (3600 * 1000)))
                        send_push_notification(
                            token=user.fcm_token,
                            title="📅 Deposit Reminder",
                            body=f"Your contribution of {ob.amount_due:,} UGX for {group.name} is due in ~{hours_left}h.",
                            data={
                                "type": "DEPOSIT_REMINDER",
                                "group_id": group.group_id,
                                "obligation_id": str(ob.id),
                                "cycle_number": str(ob.cycle_number)
                            }
                        )
                        logger.info(f"[REMINDER_WORKER] Sent {lead_hours}h reminder to {user.phone_number} for {group.name}.")

    except Exception as e:
        logger.warning(f"[REMINDER_WORKER] Error processing collection reminders: {e}")
