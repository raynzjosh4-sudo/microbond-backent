from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.investment_association import AssociationDuesExemption
from .helpers import require_member

router = APIRouter()

@router.get("/{group_id}/exemptions", summary="List fee exemptions in this association")
def list_fee_exemptions(
    group_id: str,
    active_only: bool = True,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns list of member fee exemptions.
    Admins see all exemptions; regular members see only their own.
    """
    member = require_member(group_id, current_user, session)
    query = select(AssociationDuesExemption).where(AssociationDuesExemption.group_id == group_id)

    if member.role != "ADMIN":
        query = query.where(AssociationDuesExemption.user_id == current_user.id)

    if active_only:
        query = query.where(AssociationDuesExemption.is_active == True)

    exemptions = session.exec(query).all()

    result = []
    for ex in exemptions:
        u = session.exec(select(User).where(User.id == ex.user_id)).first()
        result.append({
            "exemption_id": str(ex.id),
            "user_id": str(ex.user_id),
            "member_name": u.full_name if u else "Member",
            "exemption_type": ex.exemption_type,
            "reason": ex.reason,
            "notes": ex.notes,
            "discount_percentage": ex.discount_percentage,
            "start_date": ex.start_date,
            "end_date": ex.end_date,
            "is_active": ex.is_active,
            "created_at": ex.created_at
        })

    return {
        "status": "success",
        "count": len(result),
        "data": result
    }
