from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional, List
import uuid
from datetime import datetime, timezone

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.chat import GroupChatMessage
from app.models.group.settings import (
    GroupFinancialSettings,
    GroupGovernanceSettings,
    GroupCommunicationSettings,
    GroupVisibilitySettings,
)
from app.models.group.bill_split import BillSplitConfig, BillSplitOperationalSettings, BillSplitMemberShare
from app.schemas.bill_split_schemas import (
    BillSplitCreateRequest,
    BillSplitSettingsUpdate,
    PayBillShareRequest,
    BillSplitDashboardResponse,
    MemberShareStatus,
)

router = APIRouter(prefix="/api/v1/groups/bill-split", tags=["Bill Split Groups"])

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

# ==============================================================================
# 1. CREATE BILL SPLIT GROUP
# ==============================================================================

@router.post("/create", status_code=status.HTTP_201_CREATED)
def create_bill_split_group(
    request: BillSplitCreateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new BILL_SPLIT group.
    - Creates the base Group record (type='BILL_SPLIT', payment_mode='OBLIGATION').
    - Inserts immutable BillSplitConfig (total amount, payee, settlement deadline).
    - Inserts mutable BillSplitOperationalSettings (tip rules, auto-close, late fees).
    - Creates base GroupFinancialSettings and GroupOperationalSettings.
    - Assigns creator as ADMIN and initializes member share record.
    """
    group_id = str(uuid.uuid4())
    invite_code = str(uuid.uuid4())[:8].upper()

    # 1. Base Group
    group = Group(
        group_id=group_id,
        name=request.name,
        description=request.description or "",
        group_image_url=request.group_image_url or "",
        type="BILL_SPLIT",
        payment_mode="OBLIGATION",
        savings_term="SHORT_TERM",
        visibility=request.visibility,
        currency=request.currency,
        created_by_user_id=current_user.id,
        invite_code=invite_code,
        member_count=1,
        total_balance=0,
    )
    db.add(group)

    # 2. Creator Membership
    membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group_id,
        user_id=current_user.id,
        role="ADMIN",
        title="Organizer",
        status="ACTIVE"
    )
    db.add(membership)

    # 3. BillSplitConfig (Immutable)
    config = BillSplitConfig(
        group_id=group_id,
        total_bill_amount=request.total_bill_amount,
        split_mode=request.split_mode,
        settlement_deadline=request.settlement_deadline,
        bill_category=request.bill_category,
        payout_destination_type=request.payout_destination_type,
        payee_identifier=request.payee_identifier,
        payee_name=request.payee_name,
        bill_receipt_url=request.bill_receipt_url,
    )
    db.add(config)

    # 4. BillSplitOperationalSettings (Mutable)
    ops = BillSplitOperationalSettings(
        group_id=group_id,
        allow_tip_or_extra=request.allow_tip_or_extra,
        auto_close_on_settlement=request.auto_close_on_settlement,
        send_reminder_hours_before=request.send_reminder_hours_before,
        enable_late_fees=request.enable_late_fees,
        late_fee_amount=request.late_fee_amount,
        grace_period_hours=request.grace_period_hours,
        is_settled=False,
        total_collected=0,
        total_tip_collected=0,
    )
    db.add(ops)

    # 5. Base Settings (Synchronized)
    fin_settings = GroupFinancialSettings(
        group_id=group_id,
        enable_late_fees=request.enable_late_fees,
        late_fee_amount=float(request.late_fee_amount),
        grace_period_hours=request.grace_period_hours,
    )
    db.add(fin_settings)
    db.add(GroupGovernanceSettings(group_id=group_id))
    db.add(GroupCommunicationSettings(group_id=group_id))
    db.add(GroupVisibilitySettings(group_id=group_id))

    # 6. Initialize Creator's Share
    creator_assigned = request.total_bill_amount
    if request.member_allocations:
        for alloc in request.member_allocations:
            if alloc.user_id == current_user.id:
                creator_assigned = alloc.assigned_amount
                break

    creator_share = BillSplitMemberShare(
        group_id=group_id,
        user_id=current_user.id,
        assigned_amount=creator_assigned,
        amount_paid=0,
        tip_paid=0,
        is_settled=False,
    )
    db.add(creator_share)

    # Additional member shares if allocated upfront
    if request.member_allocations:
        for alloc in request.member_allocations:
            if alloc.user_id != current_user.id:
                member_share = BillSplitMemberShare(
                    group_id=group_id,
                    user_id=alloc.user_id,
                    assigned_amount=alloc.assigned_amount,
                    amount_paid=0,
                    tip_paid=0,
                    is_settled=False,
                )
                db.add(member_share)

    db.commit()

    return {
        "status": "success",
        "group_id": group_id,
        "invite_code": invite_code,
        "message": "Bill Split group created successfully"
    }


# ==============================================================================
# 2. BILL SPLIT DASHBOARD
# ==============================================================================

@router.get("/{group_id}/dashboard", response_model=BillSplitDashboardResponse)
def get_bill_split_dashboard(
    group_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive Bill Split dashboard overview.
    Displays total bill, collected amount, remaining balance, settlement percentage,
    deadline countdown, and member-by-member payment status.
    """
    group = db.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")
    if group.type != "BILL_SPLIT":
        raise HTTPException(status_code=400, detail="Group is not a BILL_SPLIT group.")

    # Membership check
    membership = db.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this group.")

    config = db.exec(select(BillSplitConfig).where(BillSplitConfig.group_id == group_id)).first()
    if not config:
        raise HTTPException(status_code=404, detail="Bill split configuration not found.")

    ops = db.exec(select(BillSplitOperationalSettings).where(BillSplitOperationalSettings.group_id == group_id)).first()
    if not ops:
        raise HTTPException(status_code=404, detail="Bill split operational settings not found.")

    # Balances
    remaining_balance = max(0, config.total_bill_amount - ops.total_collected)
    progress_pct = round((ops.total_collected / config.total_bill_amount) * 100.0, 1) if config.total_bill_amount > 0 else 0.0

    # Deadline
    now = utc_now()
    deadline_hours_remaining = None
    is_deadline_passed = False
    if config.settlement_deadline:
        ms_diff = config.settlement_deadline - now
        deadline_hours_remaining = round(ms_diff / (1000 * 3600), 1)
        is_deadline_passed = ms_diff < 0

    # Member Shares
    all_shares = db.exec(select(BillSplitMemberShare).where(BillSplitMemberShare.group_id == group_id)).all()
    user_ids = [s.user_id for s in all_shares]
    users_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(user_ids))).all()}
    memberships_map = {m.user_id: m for m in db.exec(select(GroupMembership).where(GroupMembership.group_id == group_id)).all()}

    members_status: List[MemberShareStatus] = []
    current_user_standing = None

    for s in all_shares:
        u = users_map.get(s.user_id)
        mem = memberships_map.get(s.user_id)
        full_name = u.full_name if u else "Unknown Member"
        phone = u.phone_number if u else None
        role = mem.role if mem else "MEMBER"
        remaining_owed = max(0, s.assigned_amount - s.amount_paid)

        stat = MemberShareStatus(
            user_id=str(s.user_id),
            full_name=full_name,
            phone_number=phone,
            role=role,
            assigned_amount=s.assigned_amount,
            amount_paid=s.amount_paid,
            tip_paid=s.tip_paid,
            remaining_owed=remaining_owed,
            is_settled=s.is_settled,
            paid_at=s.paid_at,
        )
        members_status.append(stat)
        if s.user_id == current_user.id:
            current_user_standing = stat

    return BillSplitDashboardResponse(
        group_id=group.group_id,
        name=group.name,
        description=group.description,
        currency=group.currency,
        group_image_url=group.group_image_url,
        total_bill_amount=config.total_bill_amount,
        total_collected=ops.total_collected,
        total_tip_collected=ops.total_tip_collected,
        remaining_balance=remaining_balance,
        progress_percentage=progress_pct,
        is_settled=ops.is_settled,
        settled_at=ops.settled_at,
        split_mode=config.split_mode,
        bill_category=config.bill_category,
        settlement_deadline=config.settlement_deadline,
        deadline_hours_remaining=deadline_hours_remaining,
        is_deadline_passed=is_deadline_passed,
        payout_destination_type=config.payout_destination_type,
        payee_identifier=config.payee_identifier,
        payee_name=config.payee_name,
        bill_receipt_url=config.bill_receipt_url,
        allow_tip_or_extra=ops.allow_tip_or_extra,
        auto_close_on_settlement=ops.auto_close_on_settlement,
        current_user_standing=current_user_standing,
        members=members_status,
    )


# ==============================================================================
# 3. GET & PATCH OPERATIONAL SETTINGS
# ==============================================================================

@router.get("/{group_id}/settings")
def get_bill_split_settings(
    group_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get operational settings for a BILL_SPLIT group.
    """
    membership = db.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this group.")

    ops = db.exec(select(BillSplitOperationalSettings).where(BillSplitOperationalSettings.group_id == group_id)).first()
    if not ops:
        raise HTTPException(status_code=404, detail="Bill split operational settings not found.")

    return {
        "group_id": group_id,
        "allow_tip_or_extra": ops.allow_tip_or_extra,
        "auto_close_on_settlement": ops.auto_close_on_settlement,
        "send_reminder_hours_before": ops.send_reminder_hours_before,
        "enable_late_fees": ops.enable_late_fees,
        "late_fee_amount": ops.late_fee_amount,
        "grace_period_hours": ops.grace_period_hours,
        "is_settled": ops.is_settled,
        "total_collected": ops.total_collected,
        "total_tip_collected": ops.total_tip_collected,
        "updated_at": ops.updated_at,
    }


@router.patch("/{group_id}/settings")
def update_bill_split_settings(
    group_id: str,
    request: BillSplitSettingsUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update operational settings for a BILL_SPLIT group (Admin only).
    Syncs late fee fields into base GroupFinancialSettings.
    """
    membership = db.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership or membership.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only group admins can update operational settings.")

    ops = db.exec(select(BillSplitOperationalSettings).where(BillSplitOperationalSettings.group_id == group_id)).first()
    if not ops:
        raise HTTPException(status_code=404, detail="Bill split operational settings not found.")

    if request.allow_tip_or_extra is not None:
        ops.allow_tip_or_extra = request.allow_tip_or_extra
    if request.auto_close_on_settlement is not None:
        ops.auto_close_on_settlement = request.auto_close_on_settlement
    if request.send_reminder_hours_before is not None:
        ops.send_reminder_hours_before = request.send_reminder_hours_before
    if request.enable_late_fees is not None:
        ops.enable_late_fees = request.enable_late_fees
    if request.late_fee_amount is not None:
        ops.late_fee_amount = request.late_fee_amount
    if request.grace_period_hours is not None:
        ops.grace_period_hours = request.grace_period_hours

    ops.updated_at = utc_now()
    db.add(ops)

    # Sync into base financial settings
    fin_settings = db.exec(select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)).first()
    if fin_settings:
        if request.enable_late_fees is not None:
            fin_settings.enable_late_fees = request.enable_late_fees
        if request.late_fee_amount is not None:
            fin_settings.late_fee_amount = request.late_fee_amount
        if request.grace_period_hours is not None:
            fin_settings.grace_period_hours = request.grace_period_hours
        db.add(fin_settings)

    db.commit()

    return {
        "status": "success",
        "message": "Bill Split operational settings updated successfully.",
        "settings": {
            "allow_tip_or_extra": ops.allow_tip_or_extra,
            "auto_close_on_settlement": ops.auto_close_on_settlement,
            "send_reminder_hours_before": ops.send_reminder_hours_before,
            "enable_late_fees": ops.enable_late_fees,
            "late_fee_amount": ops.late_fee_amount,
            "grace_period_hours": ops.grace_period_hours,
        }
    }


# ==============================================================================
# 4. PAY BILL SHARE
# ==============================================================================

@router.post("/{group_id}/pay-share")
def pay_bill_share(
    group_id: str,
    request: PayBillShareRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Settle a member's share (or partial share) of the bill (+ optional tip).
    Updates member share record, operational total_collected, and group total_balance.
    If 100% of the bill is collected and auto_close is enabled, marks the bill as settled!
    """
    group = db.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group or group.type != "BILL_SPLIT":
        raise HTTPException(status_code=404, detail="Bill Split group not found.")

    membership = db.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this group.")

    config = db.exec(select(BillSplitConfig).where(BillSplitConfig.group_id == group_id)).first()
    ops = db.exec(select(BillSplitOperationalSettings).where(BillSplitOperationalSettings.group_id == group_id)).first()
    if not config or not ops:
        raise HTTPException(status_code=404, detail="Bill split configuration not found.")

    if ops.is_settled:
        raise HTTPException(status_code=400, detail="This bill has already been settled.")

    # Tip check
    tip_amount = request.tip_amount if ops.allow_tip_or_extra else 0

    # Fetch or create member share record
    share = db.exec(
        select(BillSplitMemberShare).where(
            BillSplitMemberShare.group_id == group_id,
            BillSplitMemberShare.user_id == current_user.id
        )
    ).first()

    now = utc_now()
    if not share:
        # If no share record exists yet, calculate equal share if split_mode == 'EQUAL'
        assigned = config.total_bill_amount // max(1, group.member_count) if config.split_mode == "EQUAL" else request.amount
        share = BillSplitMemberShare(
            group_id=group_id,
            user_id=current_user.id,
            assigned_amount=assigned,
            amount_paid=0,
            tip_paid=0,
            is_settled=False,
        )
        db.add(share)

    # Apply payment
    share.amount_paid += request.amount
    share.tip_paid += tip_amount
    if share.amount_paid >= share.assigned_amount:
        share.is_settled = True
        share.paid_at = now
    db.add(share)

    # Update operational live counters
    ops.total_collected += request.amount
    ops.total_tip_collected += tip_amount
    ops.updated_at = now

    # Update Group balance
    group.total_balance += (request.amount + tip_amount)
    group.updated_at = now
    db.add(group)

    # Check if bill is 100% settled
    bill_closed = False
    if ops.auto_close_on_settlement and ops.total_collected >= config.total_bill_amount:
        ops.is_settled = True
        ops.settled_at = now
        bill_closed = True

    db.add(ops)

    # Group announcement
    tip_text = f" (incl. {tip_amount} {group.currency} tip)" if tip_amount > 0 else ""
    closure_text = " 🎉 The bill is now 100% settled!" if bill_closed else ""
    announcement = GroupChatMessage(
        message_id=str(uuid.uuid4()),
        group_id=group_id,
        sender_id=current_user.id,
        message_type="SYSTEM",
        message_text=f"💳 {current_user.full_name} paid {request.amount} {group.currency}{tip_text} toward their share.{closure_text}",
        created_at=now,
    )
    db.add(announcement)

    db.commit()

    return {
        "status": "success",
        "message": f"Payment of {request.amount} {group.currency} recorded successfully.{closure_text}",
        "amount_paid": request.amount,
        "tip_amount": tip_amount,
        "member_settled": share.is_settled,
        "total_bill_settled": ops.is_settled,
        "total_collected": ops.total_collected,
        "remaining_bill": max(0, config.total_bill_amount - ops.total_collected),
    }


# ==============================================================================
# 5. MARK SETTLED / CLOSE BILL (Admin only)
# ==============================================================================

@router.post("/{group_id}/mark-settled")
def mark_bill_settled(
    group_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Manually mark a bill as settled and close the split group (Admin only).
    """
    membership = db.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership or membership.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only group admins can mark the bill settled.")

    group = db.exec(select(Group).where(Group.group_id == group_id)).first()
    ops = db.exec(select(BillSplitOperationalSettings).where(BillSplitOperationalSettings.group_id == group_id)).first()
    if not group or not ops:
        raise HTTPException(status_code=404, detail="Bill split group not found.")

    now = utc_now()
    ops.is_settled = True
    ops.settled_at = now
    ops.updated_at = now
    db.add(ops)

    announcement = GroupChatMessage(
        message_id=str(uuid.uuid4()),
        group_id=group_id,
        sender_id=current_user.id,
        message_type="SYSTEM",
        message_text=f"🏁 Bill Closed: {current_user.full_name} marked this bill as settled.",
        created_at=now,
    )
    db.add(announcement)

    db.commit()

    return {
        "status": "success",
        "message": "Bill has been marked as settled.",
        "settled_at": now
    }


# ==============================================================================
# 6. REMIND DEFAULTERS (Admin only)
# ==============================================================================

@router.post("/{group_id}/remind-defaulters")
def remind_defaulters(
    group_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Send reminders to members who have not yet settled their assigned bill share.
    """
    membership = db.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership or membership.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only group admins can trigger reminders.")

    group = db.exec(select(Group).where(Group.group_id == group_id)).first()
    config = db.exec(select(BillSplitConfig).where(BillSplitConfig.group_id == group_id)).first()
    if not group or not config:
        raise HTTPException(status_code=404, detail="Bill split group not found.")

    unsettled_shares = db.exec(
        select(BillSplitMemberShare).where(
            BillSplitMemberShare.group_id == group_id,
            BillSplitMemberShare.is_settled == False
        )
    ).all()

    if not unsettled_shares:
        return {
            "status": "success",
            "message": "All members have settled their bill share! No defaulters found.",
            "unsettled_count": 0
        }

    user_ids = [s.user_id for s in unsettled_shares]
    unsettled_users = db.exec(select(User).where(User.id.in_(user_ids))).all()
    user_names = [u.full_name for u in unsettled_users if u.full_name]

    now = utc_now()
    announcement = GroupChatMessage(
        message_id=str(uuid.uuid4()),
        group_id=group_id,
        sender_id=current_user.id,
        message_type="SYSTEM",
        message_text=f"⏰ Payment Reminder: {len(unsettled_shares)} member(s) have pending shares for this bill. Please settle promptly!",
        created_at=now,
    )
    db.add(announcement)
    db.commit()

    return {
        "status": "success",
        "message": f"Reminder posted for {len(unsettled_shares)} pending member(s).",
        "unsettled_count": len(unsettled_shares),
        "unsettled_members": user_names
    }
