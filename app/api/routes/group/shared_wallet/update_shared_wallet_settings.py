import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import UpdateSharedWalletSettingsRequest
from .helpers import get_wallet, require_admin, now_ms

router = APIRouter()


@router.get("/{group_id}/settings", summary="Get shared wallet settings and operational limits")
def get_shared_wallet_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the immutable config and live operational limits for the Shared Wallet.
    """
    config, op_settings = get_wallet(group_id, session)

    allowed_types = []
    if op_settings.allowed_disbursement_types:
        try:
            allowed_types = json.loads(op_settings.allowed_disbursement_types)
        except Exception:
            allowed_types = [op_settings.allowed_disbursement_types]

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "wallet_config": config.model_dump(mode="json"),
            "operational_settings": {
                "minimum_balance_floor": op_settings.minimum_balance_floor,
                "target_budget_limit": op_settings.target_budget_limit,
                "auto_approve_threshold": op_settings.auto_approve_threshold,
                "approval_timeout_hours": op_settings.approval_timeout_hours,
                "timelock_duration_hours": op_settings.timelock_duration_hours,
                "daily_spending_cap": op_settings.daily_spending_cap,
                "per_transaction_cap": op_settings.per_transaction_cap,
                "allowed_disbursement_types": allowed_types,
                "current_balance": op_settings.current_balance,
                "total_deposited": op_settings.total_deposited,
                "total_spent": op_settings.total_spent,
                "is_active": op_settings.is_active,
            }
        }
    }


@router.patch("/{group_id}/settings", summary="Update operational limits and spend policies")
def update_shared_wallet_settings(
    group_id: str,
    request: UpdateSharedWalletSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin updates operational limits (Table 2: SharedWalletOperationalSettings).
    Core creation rules in SharedWalletConfig remain protected.
    """
    require_admin(group_id, current_user, session)
    _, op_settings = get_wallet(group_id, session)

    if request.minimum_balance_floor is not None:
        op_settings.minimum_balance_floor = request.minimum_balance_floor
    if request.target_budget_limit is not None:
        op_settings.target_budget_limit = request.target_budget_limit
    if request.auto_approve_threshold is not None:
        if request.auto_approve_threshold < 0:
            raise HTTPException(status_code=400, detail="Auto-approve threshold cannot be negative.")
        if request.auto_approve_threshold > 500000:
            raise HTTPException(status_code=400, detail="Auto-approve threshold cannot exceed 500,000 UGX.")
        op_settings.auto_approve_threshold = request.auto_approve_threshold
    if request.approval_timeout_hours is not None:
        op_settings.approval_timeout_hours = request.approval_timeout_hours
    if request.timelock_duration_hours is not None:
        op_settings.timelock_duration_hours = request.timelock_duration_hours
    if request.daily_spending_cap is not None:
        op_settings.daily_spending_cap = request.daily_spending_cap
    if request.per_transaction_cap is not None:
        op_settings.per_transaction_cap = request.per_transaction_cap
    if request.allowed_disbursement_types is not None:
        op_settings.allowed_disbursement_types = json.dumps(request.allowed_disbursement_types)

    op_settings.updated_at = now_ms()
    session.add(op_settings)
    session.commit()
    session.refresh(op_settings)

    return {
        "status": "success",
        "message": "Shared wallet settings updated successfully.",
        "data": op_settings.model_dump(mode="json")
    }
