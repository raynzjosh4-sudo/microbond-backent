from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupFinancialSettings
from app.models.group.bill_split import BillSplitOperationalSettings
from .schemas import BillSplitSettingsUpdate
from .helpers import utc_now as utc_now

router = APIRouter()

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
