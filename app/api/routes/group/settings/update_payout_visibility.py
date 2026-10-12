from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupVisibilitySettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdatePayoutVisibilityRequest(BaseModel):
    vis_manage_payout_order: Optional[bool] = None
    vis_late_fee_penalties: Optional[bool] = None
    vis_grace_period_window: Optional[bool] = None
    vis_enforce_payout_holds: Optional[bool] = None
    vis_substitute_member_allowance: Optional[bool] = None
    
    # Dues administration visibility
    vis_dues_schedule: Optional[bool] = None
    vis_allow_installments: Optional[bool] = None
    vis_arrears_policy: Optional[bool] = None
    vis_fee_exemptions: Optional[bool] = None
    vis_pending_dues_adjustments: Optional[bool] = None

    # Investment club rules & borrowing visibility
    vis_interest_rates: Optional[bool] = None
    vis_loan_guarantor_rules: Optional[bool] = None
    vis_max_borrowing_limit: Optional[bool] = None
    vis_early_repayment_discount: Optional[bool] = None
    vis_new_share_issuance: Optional[bool] = None
    vis_default_asset_seizure: Optional[bool] = None
    vis_pending_loans: Optional[bool] = None

@router.patch("/{group_id}/settings/payout-visibility", summary="Admin: Update Payout / Dues Rules Visibility")
@router.patch("/{group_id}/settings/dues-visibility", summary="Admin: Update Dues Administration Visibility")
@router.patch("/{group_id}/settings/investment-visibility", summary="Admin: Update Investment Rules Visibility")
def update_payout_visibility_settings(
    group_id: str, 
    request: UpdatePayoutVisibilityRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()
    
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update visibility settings.")

    settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Visibility settings not found.")

    if request.vis_manage_payout_order is not None:
        settings.vis_manage_payout_order = request.vis_manage_payout_order
    if request.vis_late_fee_penalties is not None:
        settings.vis_late_fee_penalties = request.vis_late_fee_penalties
    if request.vis_grace_period_window is not None:
        settings.vis_grace_period_window = request.vis_grace_period_window
    if request.vis_enforce_payout_holds is not None:
        settings.vis_enforce_payout_holds = request.vis_enforce_payout_holds
    if request.vis_substitute_member_allowance is not None:
        settings.vis_substitute_member_allowance = request.vis_substitute_member_allowance

    if request.vis_dues_schedule is not None:
        settings.vis_dues_schedule = request.vis_dues_schedule
    if request.vis_allow_installments is not None:
        settings.vis_allow_installments = request.vis_allow_installments
    if request.vis_arrears_policy is not None:
        settings.vis_arrears_policy = request.vis_arrears_policy
    if request.vis_fee_exemptions is not None:
        settings.vis_fee_exemptions = request.vis_fee_exemptions
    if request.vis_pending_dues_adjustments is not None:
        settings.vis_pending_dues_adjustments = request.vis_pending_dues_adjustments

    if request.vis_interest_rates is not None:
        settings.vis_interest_rates = request.vis_interest_rates
    if request.vis_loan_guarantor_rules is not None:
        settings.vis_loan_guarantor_rules = request.vis_loan_guarantor_rules
    if request.vis_max_borrowing_limit is not None:
        settings.vis_max_borrowing_limit = request.vis_max_borrowing_limit
    if request.vis_early_repayment_discount is not None:
        settings.vis_early_repayment_discount = request.vis_early_repayment_discount
    if request.vis_new_share_issuance is not None:
        settings.vis_new_share_issuance = request.vis_new_share_issuance
    if request.vis_default_asset_seizure is not None:
        settings.vis_default_asset_seizure = request.vis_default_asset_seizure
    if request.vis_pending_loans is not None:
        settings.vis_pending_loans = request.vis_pending_loans

    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Payout / Dues / Investment rules visibility settings updated successfully."}

