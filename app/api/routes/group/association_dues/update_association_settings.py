import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import UpdateAssociationDuesSettingsRequest
from .helpers import now_ms, require_admin, get_association

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{group_id}/settings", summary="Get association dues settings and arrears policies")
def get_association_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the association dues subscription rules and operational arrears settings.
    """
    config, settings = get_association(group_id, session)

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "association_config": config.model_dump(mode="json"),
            "operational_settings": {
                "auto_sweep_trigger": settings.auto_sweep_trigger,
                "allow_advance_payments": settings.allow_advance_payments,
                "allow_installments": settings.allow_installments,
                "grace_period_days": settings.grace_period_days,
                "late_fee_amount": settings.late_fee_amount,
                "arrears_action": settings.arrears_action,
                "max_missed_cycles_allowed": settings.max_missed_cycles_allowed,
                "show_defaulters_publicly": settings.show_defaulters_publicly,
                "treasury_ledger_visibility": settings.treasury_ledger_visibility,
                "send_arrears_reminders": settings.send_arrears_reminders,
                "arrears_reminder_days_before": settings.arrears_reminder_days_before,
                "restrict_voting_on_arrears": settings.restrict_voting_on_arrears,
                "restrict_welfare_claims_on_arrears": settings.restrict_welfare_claims_on_arrears,
                "current_balance": settings.current_balance,
                "total_collected": settings.total_collected,
                "total_swept_to_treasury": settings.total_swept_to_treasury,
                "active_defaulters_count": settings.active_defaulters_count,
                "is_active": settings.is_active,
            }
        }
    }


@router.patch("/{group_id}/settings", summary="Admin updates mutable operational settings")
def update_association_settings(
    group_id: str,
    request: UpdateAssociationDuesSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates mutable operational settings for the Association:
    - auto_sweep_trigger
    - allow_advance_payments
    - allow_installments
    - grace_period_days
    - late_fee_amount
    - arrears_action
    - max_missed_cycles_allowed
    - show_defaulters_publicly
    - treasury_ledger_visibility
    """
    require_admin(group_id, current_user, session)
    config, settings = get_association(group_id, session)

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
        logger.exception(f"Error updating association settings: {e}")
        raise HTTPException(status_code=500, detail="Database error updating settings.")

    return {
        "status": "success",
        "message": "Association settings updated successfully.",
        "data": settings.model_dump(mode="json")
    }
