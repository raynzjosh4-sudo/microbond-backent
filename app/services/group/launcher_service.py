from sqlmodel import Session
from datetime import datetime
import uuid
import logging

from app.models.group.group import Group, GroupMembership
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.settings import GroupFinancialSettings
from app.models.group.chat import GroupChatMessage
from app.services.group.matrix_generators.route_matrix_generation import route_matrix_generation

logger = logging.getLogger(__name__)

def execute_group_launch(session: Session, group_id: str) -> bool:
    """
    Executes the massive financial matrix generation to launch a group.
    Returns True if successful, False otherwise.
    """
    # 1. Row-Level Lock to prevent multiple parallel launches
    group = session.query(Group).filter(Group.group_id == group_id).with_for_update().first()
    if not group:
        return False
        
    details = session.query(RotatingGroupDetails).filter(RotatingGroupDetails.group_id == group.group_id).first()
    if not details or details.is_payout_order_locked:
        # Already launched
        return False

    # Launch Gate: Group cannot launch if contribution_amount is null or non-positive
    if details.contribution_amount is None or details.contribution_amount <= 0:
        logger.warning(f"Group {group_id} failed to launch: Contribution amount is not configured.")
        return False

    # Launch Gate: Group cannot launch if saving_days_per_cycle is null or < 1
    if details.saving_days_per_cycle is None or details.saving_days_per_cycle < 1:
        logger.warning(f"Group {group_id} failed to launch: Saving days per cycle is not configured.")
        return False
        
    settings = session.query(GroupFinancialSettings).filter(GroupFinancialSettings.group_id == group.group_id).first()
    
    # Lock all members
    all_members = session.query(GroupMembership).filter(
        GroupMembership.group_id == group.group_id
    ).with_for_update().all()
    
    # 2. Automated Purge of Pending Members
    # If the group has reached its start time, anyone still pending Guarantor approval missed the deadline.
    pending_members = [m for m in all_members if m.status in ["PENDING_APPROVAL", "PENDING_GUARANTOR"]]
    for pending in pending_members:
        session.delete(pending)
        
    # Re-evaluate active members
    active_members = [m for m in all_members if m.status == "ACTIVE"]
    
    if len(active_members) < 2:
        logger.warning(f"Group {group_id} failed to launch: Less than 2 active members after purging pendings.")
        # We might want to auto-extend the start time by 24h, but for now we just abort this launch attempt.
        return False
        
    start_date = datetime.utcnow()
    
    try:
        # 3. Generate Financial Matrix
        num_cycles = route_matrix_generation(
            session=session,
            group_id=group.group_id,
            group_type=details.payout_order_strategy,
            members=active_members,
            settings=settings,
            details=details,
            start_date=start_date
        )
        
        # 4. Lock and Activate Group
        details.is_payout_order_locked = True
        details.current_saving_day = 1
        saving_days = details.saving_days_per_cycle or 1
        details.total_expected_pool_per_cycle = details.contribution_amount * saving_days * len(active_members)
        group.status = "ACTIVE"

        from app.models.group.finance import GroupPayout, MemberObligation
        from app.models.user.user import User

        # Fetch cycle 1 recipient and due date
        payout_r1 = session.query(GroupPayout).filter(
            GroupPayout.group_id == group.group_id,
            GroupPayout.cycle_number == 1
        ).first()
        recipient_name = "Member"
        if payout_r1:
            p_user = session.get(User, payout_r1.user_id)
            if p_user and p_user.full_name:
                recipient_name = p_user.full_name

        ob_r1 = session.query(MemberObligation).filter(
            MemberObligation.group_id == group.group_id,
            MemberObligation.cycle_number == 1
        ).first()
        first_due_str = datetime.utcfromtimestamp(ob_r1.due_date / 1000).strftime('%A at %I:%M %p') if (ob_r1 and ob_r1.due_date) else "Cycle 1 Due Date"

        # Event 3: Interactive Kickoff Chat Card with Locked Cycle Terms
        curr = group.currency or "UGX"
        total_pool_str = f"{details.total_expected_pool_per_cycle:,.0f} {curr}"
        daily_amount_str = f"{details.contribution_amount:,.0f} {curr}"

        system_msg = GroupChatMessage(
            client_message_id=str(uuid.uuid4()),
            group_id=group.group_id,
            sender_id="SYSTEM",
            message_text=(
                f"🚀 The circle is full! {len(active_members)}/{group.max_members or len(active_members)} members confirmed. "
                f"🔒 Cycle 1 Terms Locked: {daily_amount_str}/day for {saving_days} saving days. "
                f"Target pool: {total_pool_str}. First collection cutoff: {first_due_str}. "
                f"Payout will be disbursed to {recipient_name}. Contributions cannot be edited while cycle is active."
            ),
            message_type="SYSTEM_EVENT",
            attachments=[{
                "has_action_button": True,
                "action_text": "View Rotation Schedule",
                "action_route": "group_rotation_schedule"
            }],
            created_at=int(start_date.timestamp() * 1000)
        )
        session.add(system_msg)

        # Event 4: Early-Turn Security Hold Disclosure
        if details.early_turn_security_hold_percentage and details.early_turn_security_hold_percentage > 0:
            security_msg = GroupChatMessage(
                client_message_id=str(uuid.uuid4()),
                group_id=group.group_id,
                sender_id="SYSTEM",
                message_text=f"🛡️ Early-Turn Security Escrow is active: A {details.early_turn_security_hold_percentage:.0f}% reserve will be held from early turns until the final cycle completes to protect members against early-turn default.",
                message_type="SYSTEM_SECURITY_NOTICE",
                attachments=[{
                    "has_action_button": True,
                    "action_text": "Learn More",
                    "action_route": "security_hold_explainer",
                    "action_payload": {
                        "hold_percentage": details.early_turn_security_hold_percentage,
                        "applicable_turns": [1, 2],
                        "release_cycle": num_cycles
                    }
                }],
                created_at=int(start_date.timestamp() * 1000) + 1
            )
            session.add(security_msg)

        if group.type == "MERRY_GO_ROUND":
            from app.services.group.rotating.prepaid_waterfall_service import advance_cycle_and_apply_prepaid
            advance_cycle_and_apply_prepaid(session, group.group_id, new_cycle=1)

        # Event 3: Push Notification Broadcast to all members
        try:
            from app.services.push_notifications import notify_all_group_members_sync
            notify_all_group_members_sync(
                group_id=group.group_id,
                sender_id="SYSTEM",
                title="🚀 Group Launched!",
                body=f"{group.name} is full and officially active! Tap to view your payout turn position.",
                data={"route": "rotation_schedule", "group_id": group.group_id}
            )
        except Exception as push_err:
            logger.warning(f"[LAUNCH PUSH BROADCAST] Failed: {push_err}")

        # Event 3: Carrier SMS (Opted-in only)
        try:
            from app.services.communication.sms.helpers.send_sms import send_sms
            for m in active_members:
                if getattr(m, "sms_reminders_opted_in", False):
                    u = session.get(User, m.user_id)
                    if u and u.phone_number:
                        send_sms(
                            u.phone_number,
                            f"Microbond: {group.name} is active! Cycle 1 collection cutoff is {first_due_str}. Your contribution is {details.contribution_amount:,} {group.currency}."
                        )
        except Exception as sms_err:
            logger.warning(f"[LAUNCH SMS] Failed: {sms_err}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to generate matrix for group {group_id}: {str(e)}")
        raise
