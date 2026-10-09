from sqlmodel import Session, select
from typing import Tuple
from uuid import UUID

from app.models.group.settings import GroupFinancialSettings
from app.models.group.finance import MemberObligation
from app.models.group.report import GroupReport

def check_payout_holds(session: Session, group_id: str, user_id: UUID) -> Tuple[bool, str]:
    """
    Evaluates if a user's payout should be placed ON_HOLD based on group rules.
    Returns: (is_held: bool, reason_for_hold: str)
    """
    # 1. Check if the group even enforces payout holds
    settings = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    
    if not settings or not settings.enforce_payout_holds:
        return False, ""
        
    # 2. Check for unpaid financial obligations (Late or Defaulted)
    unpaid_obligations = session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == group_id,
            MemberObligation.user_id == user_id,
            MemberObligation.status.in_(["LATE", "DEFAULTED"])
        )
    ).all()
    
    if unpaid_obligations:
        amount_owed = sum(obl.amount_due - obl.amount_paid for obl in unpaid_obligations)
        return True, f"User has outstanding unpaid obligations in this group totaling {amount_owed}."

    # 3. Check for serious open abuse reports against this user in this group
    open_reports = session.exec(
        select(GroupReport).where(
            GroupReport.group_id == group_id,
            GroupReport.reported_user_id == user_id,
            GroupReport.status == "OPEN"
        )
    ).all()
    
    if open_reports:
        return True, "User is currently under investigation for an open group report."

    # Passed all checks, payout is clear to send
    return False, ""
