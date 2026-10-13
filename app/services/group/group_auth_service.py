import uuid
import logging
from enum import Enum
from typing import List, Set
from sqlmodel import Session, select

from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.health import GroupHealth

from app.services.group.schemas.savings_group_type import SavingsGroupType

def evaluate_group_creation_permissions(session: Session, user_id: uuid.UUID) -> dict:
    """
    Evaluates a user's KYC tier, trust score, profile completeness, and past group health
    to determine which SavingsGroupTypes they are authorized to create, along with the 
    specific reasons for each group's status (unlocked or locked).
    """
    user = session.exec(select(User).where(User.id == user_id)).first()
    if not user:
        logger.warning(f"User {user_id} not found when evaluating group creation permissions.")
        return {
            "allowed_groups": [],
            "reasons": {},
            "allowed_group_details": [],
            "all_groups": []
        }

    base_groups = {
        SavingsGroupType.INVESTMENT_CLUB,
        SavingsGroupType.FUNDRAISER,
        SavingsGroupType.WELFARE_FUND,
        SavingsGroupType.EVENT_COMMITTEE,
        SavingsGroupType.GOAL_SAVINGS,
        SavingsGroupType.SHARED_WALLET
    }

    all_types = list(SavingsGroupType)
    allowed_types: Set[SavingsGroupType] = set()
    reasons_map: dict = {}
    group_statuses: List[dict] = []

    # Check trust factors
    is_highly_trusted = (
        user.trust_score >= 50 and
        user.is_verified and
        user.is_phone_verified and
        user.is_profile_complete and
        not user.is_dependent_account
    )

    # Check past group health for progressive unlocks
    owned_groups = session.exec(
        select(Group)
        .join(GroupMembership, Group.group_id == GroupMembership.group_id)
        .where(
            GroupMembership.user_id == user_id, 
            GroupMembership.role.in_(["OWNER", "ADMIN"])
        )
    ).all()
    
    owned_group_ids = [g.group_id for g in owned_groups]
    health_map = {}
    if owned_group_ids:
        healths = session.exec(
            select(GroupHealth).where(GroupHealth.group_id.in_(owned_group_ids))
        ).all()
        health_map = {h.group_id: h for h in healths}

    def is_group_healthy(g_type: SavingsGroupType) -> bool:
        for g in owned_groups:
            if g.type == g_type.value:
                h = health_map.get(g.group_id)
                if h and h.health_grade in ["A+", "A"] and h.risk_level == "LOW":
                    return True
        return False

    # Evaluate each group type
    for g_type in all_types:
        is_allowed = False
        reason = ""

        if user.kyc_tier < 2:
            is_allowed = False
            reason = f"Requires KYC Tier 2 verification (verified National ID / NIN). Your current KYC tier is Tier {user.kyc_tier}."

        elif g_type in base_groups:
            is_allowed = True
            reason = f"Unlocked with KYC Tier {user.kyc_tier} standard group permissions."

        elif g_type == SavingsGroupType.MERRY_GO_ROUND:
            if user.kyc_tier < 3:
                is_allowed = False
                reason = "Requires KYC Tier 3 (Biometric / Proof of Address) and Trust Score of at least 50."
            elif not is_highly_trusted:
                is_allowed = False
                if user.trust_score < 50:
                    reason = f"Requires Trust Score >= 50 (your current score is {user.trust_score})."
                elif not user.is_profile_complete:
                    reason = "Requires completing your profile details."
                elif user.is_dependent_account:
                    reason = "Dependent accounts cannot create rotating credit groups."
                else:
                    reason = "Requires high trust standing and verified status."
            else:
                is_allowed = True
                reason = f"Unlocked with KYC Tier {user.kyc_tier} and High Trust Score ({user.trust_score}/100)."

        elif g_type == SavingsGroupType.ASSOCIATION_DUES:
            if user.kyc_tier < 3 or not is_highly_trusted:
                is_allowed = False
                reason = "Requires KYC Tier 3, High Trust Score (>= 50), and managing a healthy Merry-Go-Round group."
            elif is_group_healthy(SavingsGroupType.MERRY_GO_ROUND):
                is_allowed = True
                reason = "Unlocked by successfully managing a healthy Merry-Go-Round group (Health Grade A/A+ and Low Risk)."
            else:
                is_allowed = False
                reason = "Requires owning and managing an active Merry-Go-Round group with Health Grade A/A+ and Low Risk."

        elif g_type == SavingsGroupType.BILL_SPLIT:
            if user.kyc_tier < 3 or not is_highly_trusted:
                is_allowed = False
                reason = "Requires KYC Tier 3, High Trust Score (>= 50), and managing a healthy Association Dues group."
            elif is_group_healthy(SavingsGroupType.MERRY_GO_ROUND) and is_group_healthy(SavingsGroupType.ASSOCIATION_DUES):
                is_allowed = True
                reason = "Unlocked by successfully managing an Association Dues group (Health Grade A/A+ and Low Risk)."
            else:
                is_allowed = False
                reason = "Requires owning and managing an active Association Dues group with Health Grade A/A+ and Low Risk."

        if is_allowed:
            allowed_types.add(g_type)
            reasons_map[g_type.value] = reason

        group_statuses.append({
            "type": g_type.value,
            "is_allowed": is_allowed,
            "reason": reason
        })

    allowed_list = [g.value for g in all_types if g in allowed_types]
    allowed_details = [
        {"type": g_type, "reason": reasons_map[g_type]}
        for g_type in allowed_list
    ]

    return {
        "allowed_groups": allowed_list,
        "reasons": reasons_map,
        "allowed_group_details": allowed_details,
        "all_groups": group_statuses
    }


def get_permitted_group_creation_types(session: Session, user_id: uuid.UUID) -> List[SavingsGroupType]:
    """
    Evaluates a user's permissions and returns the list of permitted SavingsGroupType enums.
    Used by create_group and other validation logic.
    """
    evaluation = evaluate_group_creation_permissions(session, user_id)
    return [SavingsGroupType(gt) for gt in evaluation["allowed_groups"]]

