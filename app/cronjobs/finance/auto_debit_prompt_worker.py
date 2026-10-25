import logging
from sqlmodel import Session, select
from datetime import datetime, timezone

from app.core.database import engine
from app.models.group.group import Group
from app.models.group.finance import MemberObligation
from app.models.group.rotating import RotatingGroupDetails
from app.models.user.user import User
from app.services.mobile_money.collection_service import initiate_mobile_money_collection
from app.utils.time.now_epoch_ms import now_epoch_ms

logger = logging.getLogger(__name__)


def process_auto_debit_prompts():
    """
    Cron Job that wakes up to trigger mobile money USSD debit prompts on member handsets
    for groups where enable_auto_debit_prompt is True and obligations are due.
    """
    now_ms = now_epoch_ms()
    one_hour_ms = 3600 * 1000

    try:
        with Session(engine) as session:
            # Query active groups with auto debit enabled
            groups = session.exec(
                select(Group, RotatingGroupDetails)
                .join(RotatingGroupDetails, Group.group_id == RotatingGroupDetails.group_id)
                .where(
                    Group.status == "ACTIVE",
                    RotatingGroupDetails.enable_auto_debit_prompt == True
                )
            ).all()

            for group, rotating in groups:
                # Obligations due today within the current window
                due_obligations = session.exec(
                    select(MemberObligation)
                    .where(
                        MemberObligation.group_id == group.group_id,
                        MemberObligation.status == "PENDING",
                        MemberObligation.due_date <= now_ms + one_hour_ms,
                        MemberObligation.due_date >= now_ms - one_hour_ms
                    )
                ).all()

                for ob in due_obligations:
                    user = session.get(User, ob.user_id)
                    if user and user.phone_number:
                        try:
                            logger.info(
                                f"[AUTO_DEBIT_WORKER] Triggering MoMo USSD prompt to {user.phone_number} "
                                f"for {ob.amount_due:,} UGX (Group: {group.name})."
                            )
                            # Call mobile money prompt gateway
                            initiate_mobile_money_collection(
                                phone_number=user.phone_number,
                                amount=ob.amount_due,
                                group_id=group.group_id,
                                obligation_id=ob.id
                            )
                        except Exception as ex:
                            logger.error(f"[AUTO_DEBIT_WORKER] Failed USSD prompt for ob {ob.id}: {ex}")

    except Exception as e:
        logger.warning(f"[AUTO_DEBIT_WORKER] Error executing auto debit prompts: {e}")
