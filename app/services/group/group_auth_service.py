import uuid
import logging
from enum import Enum
from typing import List, Set
from sqlmodel import Session, select

from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.health import GroupHealth

logger = logging.getLogger(__name__)

class SavingsGroupType(str, Enum):
    MERRY_GO_ROUND = "MERRY_GO_ROUND"
    GOAL_SAVINGS = "GOAL_SAVINGS"
    BILL_SPLIT = "BILL_SPLIT"
    WELFARE_FUND = "WELFARE_FUND"
    EVENT_COMMITTEE = "EVENT_COMMITTEE"
    INVESTMENT_CLUB = "INVESTMENT_CLUB"
    FUNDRAISER = "FUNDRAISER"
    SHARED_WALLET = "SHARED_WALLET"
    ASSOCIATION_DUES = "ASSOCIATION_DUES"

def get_permitted_group_creation_types(session: Session, user_id: uuid.UUID) -> List[SavingsGroupType]:
    """
    Evaluates a user's KYC tier, trust score, profile completeness, and past group health
    to determine which SavingsGroupTypes they are authorized to create.
    """
    user = session.exec(select(User).where(User.id == user_id)).first()
    if not user:
        logger.warning(f"User {user_id} not found when evaluating group creation permissions.")
        return []
        
    allowed_groups: Set[SavingsGroupType] = set()
    
    # RULE 1: Tier 1 KYC (or 0) sees nothing
    if user.kyc_tier < 2:
        return list(allowed_groups)
        
    # RULE 2: Base Groups for Tier 2 and restricted Tier 3
    base_groups = {
        SavingsGroupType.INVESTMENT_CLUB,
        SavingsGroupType.FUNDRAISER,
        SavingsGroupType.WELFARE_FUND,
        SavingsGroupType.EVENT_COMMITTEE,
        SavingsGroupType.GOAL_SAVINGS,
        SavingsGroupType.SHARED_WALLET
    }
    
    # Check if user is perfectly trusted
    is_highly_trusted = (
        user.trust_score >= 50 and
        user.is_verified and
        user.is_phone_verified and
        user.is_profile_complete and
        not user.is_dependent_account
    )
    
    if user.kyc_tier == 2 or (user.kyc_tier >= 3 and not is_highly_trusted):
        allowed_groups.update(base_groups)
        return list(allowed_groups)
        
    # RULE 3: Tier 3 and Highly Trusted
    if user.kyc_tier >= 3 and is_highly_trusted:
        allowed_groups.update(base_groups)
        allowed_groups.add(SavingsGroupType.MERRY_GO_ROUND)
        
        # Query for groups where this user is an OWNER or ADMIN
        owned_groups = session.exec(
            select(Group)
            .join(GroupMembership, Group.group_id == GroupMembership.group_id)
            .where(
                GroupMembership.user_id == user_id, 
                GroupMembership.role.in_(["OWNER", "ADMIN"])
            )
        ).all()
        
        owned_group_ids = [g.group_id for g in owned_groups]
        if owned_group_ids:
            # Fetch the health records for these groups
            healths = session.exec(
                select(GroupHealth).where(GroupHealth.group_id.in_(owned_group_ids))
            ).all()
            
            health_map = {h.group_id: h for h in healths}
            
            def is_group_healthy(g_type: SavingsGroupType) -> bool:
                for g in owned_groups:
                    # Map the string type from DB to our Enum for comparison
                    if g.type == g_type.value:
                        h = health_map.get(g.group_id)
                        if h and h.health_grade in ["A+", "A"] and h.risk_level == "LOW":
                            # We can also add logic here to check `g.member_count >= g.max_members` 
                            # if max_members is populated in your DB.
                            return True
                return False
                
            # RULE 4: Progressive Health Unlocks
            if is_group_healthy(SavingsGroupType.MERRY_GO_ROUND):
                allowed_groups.add(SavingsGroupType.ASSOCIATION_DUES)
                
                if is_group_healthy(SavingsGroupType.ASSOCIATION_DUES):
                    allowed_groups.add(SavingsGroupType.BILL_SPLIT)
                    # Note: INVESTMENT_CLUB is already unlocked via base_groups

    return list(allowed_groups)
