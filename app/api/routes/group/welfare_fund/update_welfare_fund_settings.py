import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import UpdateWelfareFundSettingsRequest
from .helpers import get_welfare_fund, require_admin, now_ms

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{group_id}/settings", summary="Get welfare fund settings and rules")
def get_welfare_fund_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the welfare fund constitutional rules and mutable operational settings.
    """
    config, settings = get_welfare_fund(group_id, session)

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "welfare_config": config.model_dump(mode="json"),
            "operational_settings": {
                "minimum_reserve_balance": settings.minimum_reserve_balance,
                "approval_timeout_hours": settings.approval_timeout_hours,
                "missed_payment_action": settings.missed_payment_action,
                "enable_late_fees": settings.enable_late_fees,
                "allow_annual_dividend_split": settings.allow_annual_dividend_split,
                "current_balance": settings.current_balance,
                "total_collected": settings.total_collected,
                "total_paid_out": settings.total_paid_out,
                "is_active": settings.is_active,
            }
        }
    }


@router.patch("/{group_id}/settings", summary="Admin updates mutable operational settings")
def update_welfare_fund_settings(
    group_id: str,
    request: UpdateWelfareFundSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates mutable operational settings for the Welfare Fund:
    - minimum_reserve_balance
    - approval_timeout_hours
    - missed_payment_action
    - enable_late_fees
    - allow_annual_dividend_split
    """
    require_admin(group_id, current_user, session)
    config, settings = get_welfare_fund(group_id, session)

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
        logger.exception(f"Error updating welfare settings: {e}")
        raise HTTPException(status_code=500, detail="Database error updating settings.")

    return {
        "status": "success",
        "message": "Welfare Fund settings updated successfully.",
        "data": settings.model_dump(mode="json")
    }
