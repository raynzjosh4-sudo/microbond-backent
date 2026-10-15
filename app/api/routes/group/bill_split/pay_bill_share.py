import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.chat import GroupChatMessage
from app.models.group.bill_split import BillSplitConfig, BillSplitOperationalSettings, BillSplitMemberShare
from .schemas import PayBillShareRequest
from .helpers import utc_now as utc_now

router = APIRouter()

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
