import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import UpdateSharedWalletSettingsRequest
from .helpers import get_wallet, require_admin, now_ms

router = APIRouter()

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
