from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.investment_association import AssociationMemberDuesStanding
from .helpers import require_member, now_ms as _now_ms, get_association

router = APIRouter()

@router.get("/{group_id}/dashboard", summary="View dues cycle, member standing, and treasury health")
def get_association_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full state of the Association:
    - Creation rules (Table 1)
    - Live collection trackers & treasury sweep status (Table 2)
    - Member's personal subscription & dues standing
    """
    member = require_member(group_id, current_user, session)
    config, settings = get_association(group_id, session)
    now_ms = _now_ms()

    # Member's standing
    standing = session.exec(
        select(AssociationMemberDuesStanding).where(
            AssociationMemberDuesStanding.group_id == group_id,
            AssociationMemberDuesStanding.user_id == current_user.id
        )
    ).first()

    standing_data = {
        "is_in_arrears": standing.is_in_arrears if standing else False,
        "outstanding_arrears_balance": standing.outstanding_arrears_balance if standing else 0,
        "cycles_paid_ahead": standing.cycles_paid_ahead if standing else 0,
        "is_suspended": standing.is_suspended if standing else False,
        "next_due_date": standing.next_due_date if standing else config.billing_start_date
    }

    # Ledger visibility handling
    settings_dict = settings.model_dump(mode="json")
    if settings.treasury_ledger_visibility == "ADMIN_ONLY" and member.role != "ADMIN":
        settings_dict["current_balance"] = None
        settings_dict["total_collected"] = None
        settings_dict["total_swept_to_treasury"] = None

    days_to_due = max(0, int(((standing_data["next_due_date"]) - now_ms) / (86400 * 1000)))

    return {
        "status": "success",
        "data": {
            "association_config": config.model_dump(mode="json"),
            "operational_settings": settings_dict,
            "my_standing": standing_data,
            "days_to_next_due_date": days_to_due
        }
    }
