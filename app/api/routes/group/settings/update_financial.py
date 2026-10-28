from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
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
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.services.websocket_manager import ws_manager

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
    background_tasks: BackgroundTasks = BackgroundTasks(),
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
    admin_name = current_user.full_name or "Admin"
    change_notices = []

    if request.enable_late_fees is not None and request.enable_late_fees != settings.enable_late_fees:
        settings.enable_late_fees = request.enable_late_fees
        if request.enable_late_fees:
            fee = int(request.late_fee_amount or settings.late_fee_amount or 0)
            change_notices.append(f"Late Fees: Enabled (UGX {fee:,}). Members who fail to contribute within the grace window will incur late penalties.")
        else:
            change_notices.append("Late Fees: Disabled. No penalty charges will apply for late contributions.")

    if request.late_fee_amount is not None and request.late_fee_amount != settings.late_fee_amount:
        if request.late_fee_amount < 0:
            raise HTTPException(status_code=400, detail="Late fee amount cannot be negative.")
        settings.late_fee_amount = request.late_fee_amount
        change_notices.append(f"Late Fee Amount: Set to UGX {int(request.late_fee_amount):,}.")

    if request.late_fee_frequency is not None and request.late_fee_frequency != settings.late_fee_frequency:
        settings.late_fee_frequency = request.late_fee_frequency
        change_notices.append(f"Late Fee Frequency: Set to {request.late_fee_frequency}.")

    if request.enable_grace_period is not None and request.enable_grace_period != settings.enable_grace_period:
        settings.enable_grace_period = request.enable_grace_period
        hrs = request.grace_period_hours or settings.grace_period_hours or 0
        if request.enable_grace_period:
            change_notices.append(f"Grace Period: Enabled ({hrs} hours). Members have {hrs} hours after the deadline before late fees or arrears apply.")
        else:
            change_notices.append("Grace Period: Disabled. Contributions are due strictly at the collection deadline.")

    if request.grace_period_hours is not None and request.grace_period_hours != settings.grace_period_hours:
        if request.grace_period_hours < 0:
            raise HTTPException(status_code=400, detail="Grace period hours cannot be negative.")
        settings.grace_period_hours = request.grace_period_hours
        change_notices.append(f"Grace Period Duration: Set to {request.grace_period_hours} hours.")

    if request.arrears_policy is not None and request.arrears_policy != settings.arrears_policy:
        settings.arrears_policy = request.arrears_policy
        change_notices.append(f"Arrears Policy: Updated to '{request.arrears_policy}'.")

    if request.reserve_fund_percentage is not None and request.reserve_fund_percentage != settings.reserve_fund_percentage:
        if request.reserve_fund_percentage < 0 or request.reserve_fund_percentage > 100:
            raise HTTPException(status_code=400, detail="Reserve fund percentage must be between 0 and 100.")
        settings.reserve_fund_percentage = request.reserve_fund_percentage
        change_notices.append(f"Reserve Fund: Set to {request.reserve_fund_percentage}% retained for group emergency buffer.")

    if request.allow_substitute_members is not None and request.allow_substitute_members != settings.allow_substitute_members:
        settings.allow_substitute_members = request.allow_substitute_members
        if request.allow_substitute_members:
            change_notices.append("Substitute Members: Enabled. Members facing hardship may nominate a vetted substitute.")
        else:
            change_notices.append("Substitute Members: Disabled.")

    if request.enforce_payout_holds is not None and request.enforce_payout_holds != settings.enforce_payout_holds:
        settings.enforce_payout_holds = request.enforce_payout_holds
        if request.enforce_payout_holds:
            change_notices.append("Payout Holds: Enabled. Defaulters will have payouts paused until arrears are fully cleared.")
        else:
            change_notices.append("Payout Holds: Disabled.")

    if request.max_pending_payouts is not None and request.max_pending_payouts != settings.max_pending_payouts:
        if request.max_pending_payouts < 1:
            raise HTTPException(status_code=400, detail="Max pending payouts must be at least 1.")
        settings.max_pending_payouts = request.max_pending_payouts
        change_notices.append(f"Max Pending Payouts: Set to {request.max_pending_payouts}.")

    if request.enable_escrow is not None and request.enable_escrow != settings.enable_escrow:
        settings.enable_escrow = request.enable_escrow
        if request.enable_escrow:
            change_notices.append("Escrow Protection: Enabled. Pool disbursements require escrow conditions to be satisfied.")
        else:
            change_notices.append("Escrow Protection: Disabled.")

    if request.escrow_release_condition is not None and request.escrow_release_condition != settings.escrow_release_condition:
        settings.escrow_release_condition = request.escrow_release_condition
        change_notices.append(f"Escrow Release Condition: Updated to '{request.escrow_release_condition}'.")

    if request.enable_timelock is not None and request.enable_timelock != settings.enable_timelock:
        settings.enable_timelock = request.enable_timelock
        hrs = request.timelock_duration_hours or settings.timelock_duration_hours or 0
        if request.enable_timelock:
            change_notices.append(f"Timelock Security: Enabled ({hrs} hours). Disbursals are subject to a {hrs}-hour delay before release.")
        else:
            change_notices.append("Timelock Security: Disabled.")

    if request.timelock_duration_hours is not None and request.timelock_duration_hours != settings.timelock_duration_hours:
        if request.timelock_duration_hours < 0:
            raise HTTPException(status_code=400, detail="Timelock duration hours cannot be negative.")
        settings.timelock_duration_hours = request.timelock_duration_hours
        change_notices.append(f"Timelock Duration: Set to {request.timelock_duration_hours} hours.")

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

    if change_notices:
        bullet_points = "\n".join(f"• {c}" for c in change_notices)
        system_text = f"💰 Financial Settings Updated by {admin_name}:\n{bullet_points}"
        system_msg = broadcast_system_message_sync(
            group_id=group_id,
            message_text=system_text,
            message_type="SYSTEM_EVENT",
            sender_id="SYSTEM",
            session=session,
            background_tasks=background_tasks,
            attachments=[{
                "category": "SETTINGS_UPDATE",
                "setting_type": "FINANCIAL",
                "admin_id": str(current_user.id),
                "admin_name": admin_name,
                "changes_count": len(change_notices)
            }]
        )
        if background_tasks is None and system_msg:
            try:
                import asyncio
                asyncio.create_task(
                    ws_manager.broadcast_to_group(
                        group_id,
                        {
                            "event_type": "NEW_MESSAGE",
                            "message": system_msg.model_dump(mode="json")
                        }
                    )
                )
            except Exception:
                pass

    return {
        "status": "success",
        "message": "Financial settings updated.",
        "synced_to_type": group.type
    }
