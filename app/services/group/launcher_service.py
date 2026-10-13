from sqlmodel import Session
from datetime import datetime
import uuid
import logging

from app.models.group.group import Group, GroupMembership
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.settings import GroupFinancialSettings
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
        group.status = "ACTIVE"
        
        # 5. Broadcast to Group Chat
        system_msg = GroupChatMessage(
            message_id=str(uuid.uuid4()),
            group_id=group.group_id,
            sender_id=None,
            content=f"🚀 The group cycle has automatically launched! The schedule has been generated for {num_cycles} cycles. Any members who did not secure a Guarantor in time have been removed.",
            message_type="SYSTEM",
            created_at=int(start_date.timestamp())
        )
        session.add(system_msg)
        
        return True
    except Exception as e:
        logger.error(f"Failed to generate matrix for group {group_id}: {str(e)}")
        raise
