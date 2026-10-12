from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupFinancialSettings
from app.models.group.long_term import TargetSavingsGroupDetails
from app.models.group.welfare_event import WelfareFundOperationalSettings
from app.models.group.investment_association import (
    InvestmentClubOperationalSettings,
    AssociationDuesOperationalSettings
)
from app.models.group.bill_split import BillSplitOperationalSettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateGeneralSettingsRequest(BaseModel):
    # Group identity
    name: Optional[str] = None
    description: Optional[str] = None
    maximum_member_capacity: Optional[int] = None

    # Financial rules — shared across group types
    enable_late_fees: Optional[bool] = None
    late_fee_amount: Optional[int] = None        # whole integer (e.g. 5000 UGX)
    grace_period_hours: Optional[int] = None
    reserve_fund_percentage: Optional[float] = None

@router.patch("/{group_id}/settings/general", summary="Update Group Settings")
def update_group_settings(
    group_id: str,
    request: UpdateGeneralSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates general group settings.
    Fields that overlap with group-type-specific tables
    (GOAL_SAVINGS, MERRY_GO_ROUND, SHARED_WALLET) are automatically
    synced into the relevant specific table so both stay consistent.
    """
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update settings.")

    # ── 1. Group table fields ─────────────────────────────────────────────────
    if request.name is not None:
        group.name = request.name
    if request.description is not None:
        group.description = request.description
    if request.maximum_member_capacity is not None:
        current_members = session.exec(
            select(GroupMembership).where(GroupMembership.group_id == group_id)
        ).all()
        if request.maximum_member_capacity < len(current_members):
            raise HTTPException(
                status_code=400,
                detail="Cannot lower capacity below the current number of joined members."
            )
        group.max_members = request.maximum_member_capacity
    session.add(group)

    # ── 2. Base financial settings (applies to ALL group types) ──────────────
    fin = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    if fin:
        if request.enable_late_fees is not None:
            fin.enable_late_fees = request.enable_late_fees
        if request.late_fee_amount is not None:
            fin.late_fee_amount = float(request.late_fee_amount)
        if request.grace_period_hours is not None:
            fin.grace_period_hours = request.grace_period_hours
        if request.reserve_fund_percentage is not None:
            fin.reserve_fund_percentage = request.reserve_fund_percentage
        session.add(fin)

    # ── 3. Sync duplicated fields into group-type-specific tables ─────────────
    # GOAL_SAVINGS: enable_late_fees, late_fee_amount, grace_period_hours are
    # duplicated in TargetSavingsGroupDetails — keep them in sync.
    if group.type == "GOAL_SAVINGS":
        target = session.exec(
            select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
        ).first()
        if target:
            if request.enable_late_fees is not None:
                target.enable_late_fees = request.enable_late_fees
            if request.late_fee_amount is not None:
                target.late_fee_amount = request.late_fee_amount
            if request.grace_period_hours is not None:
                target.grace_period_hours = request.grace_period_hours
            session.add(target)

    elif group.type == "WELFARE_FUND":
        welfare = session.exec(
            select(WelfareFundOperationalSettings).where(
                WelfareFundOperationalSettings.group_id == group_id
            )
        ).first()
        if welfare:
            if request.enable_late_fees is not None:
                welfare.enable_late_fees = request.enable_late_fees
                session.add(welfare)

    elif group.type == "INVESTMENT_CLUB":
        club = session.exec(
            select(InvestmentClubOperationalSettings).where(
                InvestmentClubOperationalSettings.group_id == group_id
            )
        ).first()
        if club:
            if request.enable_late_fees is not None:
                club.enable_late_fees = request.enable_late_fees
                session.add(club)

    elif group.type == "ASSOCIATION_DUES":
        assoc = session.exec(
            select(AssociationDuesOperationalSettings).where(
                AssociationDuesOperationalSettings.group_id == group_id
            )
        ).first()
        if assoc:
            if request.late_fee_amount is not None:
                assoc.late_fee_amount = request.late_fee_amount
                session.add(assoc)

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
                bill.late_fee_amount = request.late_fee_amount
            if request.grace_period_hours is not None:
                bill.grace_period_hours = request.grace_period_hours
            session.add(bill)

    session.commit()
    return {
        "status": "success",
        "message": "General settings updated.",
        "synced_to_type": group.type
    }
