from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.bill_split import BillSplitOperationalSettings

router = APIRouter()

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
