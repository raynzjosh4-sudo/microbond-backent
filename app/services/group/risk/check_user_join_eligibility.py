from fastapi import HTTPException
from sqlmodel import Session
from sqlalchemy import func

from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupGovernanceSettings
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.finance import GroupPayout, MemberObligation, GroupPenalty, GuarantorPledge


def check_user_join_eligibility(
    user: User,
    group: Group,
    settings: GroupGovernanceSettings,
    session: Session,
    guarantor_ids: list[str] = None
) -> bool:
    """
    Executes all cross-group financial risk checks to ensure a user is eligible to join a group.
    Raises an HTTPException if the user fails any check.
    """
    active_rotating_groups = session.query(GroupMembership).join(Group).filter(
        GroupMembership.user_id == user.id,
        GroupMembership.status == "ACTIVE",
        Group.type == "MERRY_GO_ROUND"
    ).count()

    if group.type == "MERRY_GO_ROUND" and active_rotating_groups >= 10:
        raise HTTPException(
            status_code=403,
            detail="You are already in 10 active rotating groups. You cannot join any more until your current cycles finish."
        )

    hit_and_run_payout = session.query(GroupPayout).join(
        GroupMembership,
        (GroupPayout.group_id == GroupMembership.group_id) & (GroupPayout.user_id == GroupMembership.user_id)
    ).filter(
        GroupPayout.user_id == user.id,
        GroupMembership.status == "ACTIVE",
        GroupPayout.status == "COMPLETED"
    ).first()

    if hit_and_run_payout:
        unpaid_obligations = session.query(MemberObligation).filter(
            MemberObligation.user_id == user.id,
            MemberObligation.group_id == hit_and_run_payout.group_id,
            MemberObligation.cycle_number == hit_and_run_payout.cycle_number,
            MemberObligation.status != "PAID"
        ).count()

        if unpaid_obligations > 0:
            raise HTTPException(
                status_code=403,
                detail="You have received a payout in another group but still owe contributions to that cycle. You cannot join a new group until you clear your debts."
            )

    late_obligations = session.query(MemberObligation).filter(
        MemberObligation.user_id == user.id,
        MemberObligation.status == "LATE"
    ).count()

    if late_obligations > 0:
        raise HTTPException(
            status_code=403,
            detail="You currently have an unpaid missed payment or arrears in another group. Please settle it before joining a new group."
        )

    if group.type == "MERRY_GO_ROUND":
        historical_penalties = session.query(GroupPenalty).filter(
            GroupPenalty.user_id == user.id
        ).count()

        if historical_penalties >= 3:
            raise HTTPException(
                status_code=403,
                detail="Your account has a history of slow payments (3 or more penalties). You are restricted from joining new Rotating Groups."
            )

    if settings.minimum_trust_score is not None:
        if user.trust_score < settings.minimum_trust_score:
            raise HTTPException(
                status_code=403,
                detail=f"Your Trust Score ({user.trust_score}) is below the required {settings.minimum_trust_score}."
            )

    if settings.require_guarantors:
        unique_guarantors = set(guarantor_ids) if guarantor_ids else set()

        if len(unique_guarantors) < settings.guarantor_count:
            raise HTTPException(status_code=400, detail=f"This group strictly requires exactly {settings.guarantor_count} unique Guarantor(s).")

        for gid in unique_guarantors:
            if gid == str(user.id):
                raise HTTPException(status_code=400, detail="You cannot be your own guarantor.")

            guarantor_membership = session.query(GroupMembership).filter(
                GroupMembership.group_id == group.group_id,
                GroupMembership.user_id == gid,
                GroupMembership.status == "ACTIVE"
            ).first()

            if not guarantor_membership:
                raise HTTPException(status_code=400, detail="One or more selected guarantors are not active members of this group.")

            guarantor_user = session.query(User).filter(User.id == gid).first()
            if not guarantor_user:
                raise HTTPException(status_code=400, detail="Guarantor user account not found.")

            guarantor_trust = guarantor_user.trust_score or 50
            if guarantor_trust < 70:
                raise HTTPException(
                    status_code=403,
                    detail=f"Guarantor {guarantor_user.full_name} has a Trust Score of {guarantor_trust}. A minimum of 70 is required to vouch for others."
                )

            bad_obligations = session.query(MemberObligation).filter(
                MemberObligation.user_id == gid,
                MemberObligation.status.in_(["LATE", "DEFAULTED"])
            ).count()

            if bad_obligations > 0:
                raise HTTPException(
                    status_code=403,
                    detail=f"Guarantor {guarantor_user.full_name} currently has overdue or defaulted payments and cannot take on risk."
                )

            total_active_liability = session.query(func.sum(GuarantorPledge.maximum_liability_amount)).filter(
                GuarantorPledge.guarantor_user_id == gid,
                GuarantorPledge.status.in_(["ACTIVE", "PENDING_CONSENT"])
            ).scalar() or 0.0

            base_allowance = 500000.0
            historical_weight = (guarantor_membership.total_contributed * 5) * (guarantor_trust / 100.0)
            dynamic_max_liability = max(base_allowance, historical_weight)

            if total_active_liability >= dynamic_max_liability:
                raise HTTPException(
                    status_code=403,
                    detail=f"Guarantor {guarantor_user.full_name} is over-leveraged. Their dynamic risk capacity is {dynamic_max_liability:,.0f} UGX."
                )

    if group.type == "MERRY_GO_ROUND":
        rotating_details = session.query(RotatingGroupDetails).filter(RotatingGroupDetails.group_id == group.group_id).first()
        if user.kyc_tier < rotating_details.minimum_kyc_tier:
            raise HTTPException(
                status_code=403,
                detail=f"You need KYC Tier {rotating_details.minimum_kyc_tier} to join this rotating group."
            )
        if rotating_details.is_payout_order_locked:
            raise HTTPException(status_code=400, detail="The payout cycle has already started. You cannot join mid-way.")

    return True
