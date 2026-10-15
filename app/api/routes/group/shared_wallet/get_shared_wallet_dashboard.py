import json
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group
from app.models.user.user import User
from .helpers import get_wallet, require_member

router = APIRouter()

@router.get("/{group_id}/dashboard", summary="View shared wallet status, balance, and limits")
def get_shared_wallet_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full state of the shared wallet:
    - Creation configuration rules (Table 1)
    - Live operational settings & spend limits (Table 2)
    - Current balance and cumulative totals
    """
    require_member(group_id, current_user, session)
    config, op_settings = get_wallet(group_id, session)

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()

    # Parse allowed disbursement types
    try:
        allowed_types = json.loads(op_settings.allowed_disbursement_types)
    except Exception:
        allowed_types = ["MEMBER_ACCOUNTS", "EXTERNAL_PAYEES"]

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "name": group.name if group else "",
            "currency": group.currency if group else "UGX",
            "current_balance": op_settings.current_balance,
            "minimum_balance_floor": op_settings.minimum_balance_floor,
            "spendable_balance": max(0, op_settings.current_balance - op_settings.minimum_balance_floor),
            "total_deposited": op_settings.total_deposited,
            "total_spent": op_settings.total_spent,
            "is_active": op_settings.is_active,
            "config": config.model_dump(mode="json"),
            "operational_settings": {
                **op_settings.model_dump(mode="json"),
                "allowed_disbursement_types": allowed_types
            }
        }
    }
