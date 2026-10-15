from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.bill_split import BillSplitConfig, BillSplitOperationalSettings, BillSplitMemberShare
from .schemas import BillSplitDashboardResponse, MemberShareStatus
from .helpers import utc_now as utc_now

router = APIRouter()

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
