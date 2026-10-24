import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import UpdateInvestmentClubSettingsRequest
from .helpers import require_admin, get_club, now_ms

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{group_id}/settings", summary="Get investment club settings and credit rules")
def get_investment_club_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the investment club constitutional rules and mutable operational settings.
    """
    config, settings = get_club(group_id, session)

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "investment_config": config.model_dump(mode="json"),
            "operational_settings": {
                "minimum_purchase_quota": settings.minimum_purchase_quota,
                "proposal_approval_threshold_pct": settings.proposal_approval_threshold_pct,
                "admin_management_fee_pct": settings.admin_management_fee_pct,
                "allow_internal_share_transfers": settings.allow_internal_share_transfers,
                "enable_late_fees": settings.enable_late_fees,
                "interest_rate_mode": settings.interest_rate_mode,
                "fixed_interest_rate_pct": settings.fixed_interest_rate_pct,
                "require_loan_guarantors": settings.require_loan_guarantors,
                "min_loan_guarantors": settings.min_loan_guarantors,
                "max_borrowing_limit": settings.max_borrowing_limit,
                "early_repayment_discount_pct": settings.early_repayment_discount_pct,
                "new_share_issuance_mode": settings.new_share_issuance_mode,
                "default_recovery_action": settings.default_recovery_action,
                "contribution_reminder_days_before": settings.contribution_reminder_days_before,
                "auto_debit_consent_required": settings.auto_debit_consent_required,
                "emergency_contact_name": settings.emergency_contact_name,
                "emergency_contact_phone": settings.emergency_contact_phone,
                "liquidity_buffer_coverage_pct": settings.liquidity_buffer_coverage_pct,
                "enable_late_fee_escalation": settings.enable_late_fee_escalation,
                "enable_sms_call_reminders": settings.enable_sms_call_reminders,
                "current_balance": settings.current_balance,
                "total_invested_capital": settings.total_invested_capital,
                "total_shares_issued": settings.total_shares_issued,
                "total_dividends_distributed": settings.total_dividends_distributed,
                "active_loans_count": settings.active_loans_count,
                "total_loans_disbursed": settings.total_loans_disbursed,
                "is_active": settings.is_active,
            }
        }
    }


@router.patch("/{group_id}/settings", summary="Admin updates mutable club settings")
def update_investment_club_settings(
    group_id: str,
    request: UpdateInvestmentClubSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates mutable operational settings for the Investment Club:
    - minimum_purchase_quota
    - proposal_approval_threshold_pct
    - admin_management_fee_pct
    - allow_internal_share_transfers
    - enable_late_fees
    - internal lending & credit rules
    - fund stability & reminders
    """
    require_admin(group_id, current_user, session)
    config, settings = get_club(group_id, session)

    update_dict = request.model_dump(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid settings provided to update.")

    for field, val in update_dict.items():
        if hasattr(settings, field) and val is not None:
            setattr(settings, field, val)

    settings.updated_at = now_ms()
    session.add(settings)

    try:
        session.commit()
        session.refresh(settings)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error updating investment club settings: {e}")
        raise HTTPException(status_code=500, detail="Database error updating settings.")

    return {
        "status": "success",
        "message": "Investment club settings updated successfully.",
        "data": settings.model_dump(mode="json")
    }
