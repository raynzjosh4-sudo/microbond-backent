import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlmodel import Session, select

from app.models.group.group import Group, GroupMembership
from app.models.group.finance import GroupPayout, MemberObligation
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.wallet import GroupWallet
from app.services.group.matrix_generators.standard_fixed import generate_standard_fixed_matrix
from app.models.group.settings import GroupFinancialSettings
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.utils.time.now_epoch_ms import now_epoch_ms

logger = logging.getLogger(__name__)


def execute_cycle_renewal(
    session: Session,
    group_id: str,
    rotating: RotatingGroupDetails,
    now_ms: Optional[int] = None
) -> bool:
    """
    Executes automated cycle renewal when all rounds in the previous cycle finish.
    Inverts payout order if reverse_payout_order_on_renew is True, releases
    held security reserves, advances current_cycle, and generates the new matrix.
    """
    if now_ms is None:
        now_ms = now_epoch_ms()

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        logger.error(f"[CYCLE_RENEWAL] Group {group_id} not found.")
        return False

    prev_cycle_number = rotating.current_cycle

    # 1. Fetch previous cycle payouts to determine roster sequence
    prev_payouts = session.exec(
        select(GroupPayout)
        .where(GroupPayout.group_id == group_id)
        .order_by(GroupPayout.cycle_number.asc())
    ).all()

    if not prev_payouts:
        logger.warning(f"[CYCLE_RENEWAL] No previous payouts found for group {group_id}.")
        return False

    # Get ordered unique user IDs from previous cycle
    ordered_users: List = []
    seen = set()
    for p in prev_payouts:
        if p.user_id not in seen:
            seen.add(p.user_id)
            ordered_users.append(p.user_id)

    # 2. Invert payout order if configured
    if rotating.reverse_payout_order_on_renew:
        ordered_users = list(reversed(ordered_users))
        logger.info(f"[CYCLE_RENEWAL] Reversed roster order for group {group_id} Cycle {prev_cycle_number + 1}.")

    # Fetch active group memberships in that exact order
    active_members_dict = {
        m.user_id: m for m in session.exec(
            select(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.status == "ACTIVE"
            )
        ).all()
    }

    renewal_members = [
        active_members_dict[uid]
        for uid in ordered_users
        if uid in active_members_dict
    ]

    if len(renewal_members) < 2:
        logger.warning(f"[CYCLE_RENEWAL] Group {group_id} has fewer than 2 active members. Cannot renew.")
        group.status = "COMPLETED"
        session.add(group)
        session.commit()
        return False

    # 3. Release any early turn security hold reserves from completed cycle
    wallet = session.exec(
        select(GroupWallet).where(GroupWallet.group_id == group_id)
    ).first()

    for p in prev_payouts:
        if p.amount_received < p.amount_expected and p.hold_reason and "Security reserve" in p.hold_reason:
            held_amount = p.amount_expected - p.amount_received
            # Check if this user had any unpaid/late obligations in that cycle
            unpaid_count = session.exec(
                select(MemberObligation).where(
                    MemberObligation.group_id == group_id,
                    MemberObligation.user_id == p.user_id,
                    MemberObligation.status.in_(["LATE", "MISSED"])
                )
            ).all()

            if not unpaid_count and held_amount > 0 and wallet and wallet.reserve_funds >= held_amount:
                # Release held reserve back to the member
                wallet.reserve_funds -= held_amount
                wallet.total_lifetime_payouts += held_amount
                p.amount_received = p.amount_expected
                p.hold_reason = "Security reserve fully refunded upon cycle completion."
                session.add(p)
                session.add(wallet)
                logger.info(f"[CYCLE_RENEWAL] Released held security reserve of {held_amount:,} UGX to user {p.user_id}.")

    # 4. Advance Cycle Counter
    rotating.current_cycle += 1
    session.add(rotating)

    # 5. Generate New Obligations & Payouts for Cycle 2
    settings = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()

    freq_days = rotating.collection_frequency_days or 7
    next_start_date = datetime.now(timezone.utc) + timedelta(days=freq_days)

    generate_standard_fixed_matrix(
        session=session,
        group_id=group_id,
        members=renewal_members,
        settings=settings,
        details=rotating,
        start_date=next_start_date
    )

    session.commit()

    # 6. Post Announcement Message in Group Chat
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=(
            f"🎉 Cycle {prev_cycle_number} has concluded successfully! "
            f"Cycle {rotating.current_cycle} is now active with updated turn order."
        ),
        message_type="SYSTEM_EVENT",
        sender_id=str(group.created_by_user_id),
        session=session
    )

    logger.info(f"[CYCLE_RENEWAL] Successfully renewed group {group_id} to Cycle {rotating.current_cycle}.")
    return True
