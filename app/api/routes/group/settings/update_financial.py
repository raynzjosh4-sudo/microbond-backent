from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupFinancialSettings
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.long_term import TargetSavingsGroupDetails, SharedWalletOperationalSettings
from app.models.group.welfare_event import WelfareFundOperationalSettings
from app.models.group.investment_association import (
    InvestmentClubOperationalSettings,
    AssociationDuesOperationalSettings
)
from app.models.group.bill_split import BillSplitOperationalSettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateFinancialSettingsRequest(BaseModel):
    enable_late_fees: Optional[bool] = None
    late_fee_amount: Optional[float] = None
    late_fee_frequency: Optional[str] = None

    enable_grace_period: Optional[bool] = None
    grace_period_hours: Optional[int] = None

    arrears_policy: Optional[str] = None
    reserve_fund_percentage: Optional[float] = None
    allow_substitute_members: Optional[bool] = None
    enforce_payout_holds: Optional[bool] = None
    max_pending_payouts: Optional[int] = None

    enable_escrow: Optional[bool] = None
    escrow_release_condition: Optional[str] = None
    enable_timelock: Optional[bool] = None
    timelock_duration_hours: Optional[int] = None

@router.patch("/{group_id}/settings/financial", summary="Admin: Update Financial Settings")
def update_financial_settings(
    group_id: str,
    request: UpdateFinancialSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates base financial settings that apply to all group types.
    Overlapping fields are automatically synced into group-type-specific tables:
    - MERRY_GO_ROUND: enforce_payout_holds → RotatingGroupDetails
    - SHARED_WALLET:  timelock_duration_hours → SharedWalletOperationalSettings
    """
    # Verify admin
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update financial settings.")

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    settings = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    if not settings:
        raise HTTPException(status_code=404, detail="Financial settings not found.")

    # ── 1. Apply to base GroupFinancialSettings ──────────────────────────────
    if request.enable_late_fees is not None:
        settings.enable_late_fees = request.enable_late_fees
    if request.late_fee_amount is not None:
        if request.late_fee_amount < 0:
            raise HTTPException(status_code=400, detail="Late fee amount cannot be negative.")
        settings.late_fee_amount = request.late_fee_amount
    if request.late_fee_frequency is not None:
        settings.late_fee_frequency = request.late_fee_frequency

    if request.enable_grace_period is not None:
        settings.enable_grace_period = request.enable_grace_period
    if request.grace_period_hours is not None:
        if request.grace_period_hours < 0:
            raise HTTPException(status_code=400, detail="Grace period hours cannot be negative.")
        settings.grace_period_hours = request.grace_period_hours

    if request.arrears_policy is not None:
        settings.arrears_policy = request.arrears_policy
    if request.reserve_fund_percentage is not None:
        if request.reserve_fund_percentage < 0 or request.reserve_fund_percentage > 100:
            raise HTTPException(status_code=400, detail="Reserve fund percentage must be between 0 and 100.")
        settings.reserve_fund_percentage = request.reserve_fund_percentage
    if request.allow_substitute_members is not None:
        settings.allow_substitute_members = request.allow_substitute_members
    if request.enforce_payout_holds is not None:
        settings.enforce_payout_holds = request.enforce_payout_holds
    if request.max_pending_payouts is not None:
        if request.max_pending_payouts < 1:
            raise HTTPException(status_code=400, detail="Max pending payouts must be at least 1.")
        settings.max_pending_payouts = request.max_pending_payouts

    if request.enable_escrow is not None:
        settings.enable_escrow = request.enable_escrow
    if request.escrow_release_condition is not None:
        settings.escrow_release_condition = request.escrow_release_condition
    if request.enable_timelock is not None:
        settings.enable_timelock = request.enable_timelock
    if request.timelock_duration_hours is not None:
        if request.timelock_duration_hours < 0:
            raise HTTPException(status_code=400, detail="Timelock duration hours cannot be negative.")
        settings.timelock_duration_hours = request.timelock_duration_hours

    session.add(settings)

    # ── 2. Sync duplicated fields into type-specific tables ───────────────────
    # MERRY_GO_ROUND: enforce_payout_holds duplicated in RotatingGroupDetails
    if group.type == "MERRY_GO_ROUND":
        rotating = session.exec(
            select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
        ).first()
        if rotating and request.enforce_payout_holds is not None:
            rotating.enforce_payout_holds = request.enforce_payout_holds
            session.add(rotating)

    # SHARED_WALLET: timelock_duration_hours duplicated in SharedWalletOperationalSettings
    elif group.type == "SHARED_WALLET":
        ops = session.exec(
            select(SharedWalletOperationalSettings).where(
                SharedWalletOperationalSettings.group_id == group_id
            )
        ).first()
        if ops and request.timelock_duration_hours is not None:
            ops.timelock_duration_hours = request.timelock_duration_hours
            session.add(ops)

    # GOAL_SAVINGS: enable_late_fees, late_fee_amount, grace_period_hours in TargetSavingsGroupDetails
    elif group.type == "GOAL_SAVINGS":
        target = session.exec(
            select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
        ).first()
        if target:
            if request.enable_late_fees is not None:
                target.enable_late_fees = request.enable_late_fees
            if request.late_fee_amount is not None:
                target.late_fee_amount = int(request.late_fee_amount)
            if request.grace_period_hours is not None:
                target.grace_period_hours = request.grace_period_hours
            session.add(target)

    # WELFARE_FUND: enable_late_fees in WelfareFundOperationalSettings
    elif group.type == "WELFARE_FUND":
        welfare = session.exec(
            select(WelfareFundOperationalSettings).where(
                WelfareFundOperationalSettings.group_id == group_id
            )
        ).first()
        if welfare and request.enable_late_fees is not None:
            welfare.enable_late_fees = request.enable_late_fees
            session.add(welfare)

    # INVESTMENT_CLUB: enable_late_fees in InvestmentClubOperationalSettings
    elif group.type == "INVESTMENT_CLUB":
        club = session.exec(
            select(InvestmentClubOperationalSettings).where(
                InvestmentClubOperationalSettings.group_id == group_id
            )
        ).first()
        if club and request.enable_late_fees is not None:
            club.enable_late_fees = request.enable_late_fees
            session.add(club)

    # ASSOCIATION_DUES: late_fee_amount in AssociationDuesOperationalSettings
    elif group.type == "ASSOCIATION_DUES":
        assoc = session.exec(
            select(AssociationDuesOperationalSettings).where(
                AssociationDuesOperationalSettings.group_id == group_id
            )
        ).first()
        if assoc and request.late_fee_amount is not None:
            assoc.late_fee_amount = int(request.late_fee_amount)
            session.add(assoc)

    # BILL_SPLIT: enable_late_fees, late_fee_amount, grace_period_hours in BillSplitOperationalSettings
    elif group.type == "BILL_SPLIT":
        bill = session.exec(
            select(BillSplitOperationalSettings).where(
                BillSplitOperationalSettings.group_id == group_id
            )
        ).first()
        if bill:
            if request.enable_late_fees is not None:
                bill.enable_late_fees = request.enable_late_fees
            if request.late_fee_amount is not None:
                bill.late_fee_amount = int(request.late_fee_amount)
            if request.grace_period_hours is not None:
                bill.grace_period_hours = request.grace_period_hours
            session.add(bill)

    session.commit()
    return {
        "status": "success",
        "message": "Financial settings updated.",
        "synced_to_type": group.type
    }
