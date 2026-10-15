from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.investment_association import AssociationMemberDuesStanding
from .helpers import require_member, get_association

router = APIRouter()

@router.get("/{group_id}/defaulters", summary="List members currently in arrears")
def list_defaulters(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns list of members in arrears.
    Accessible to admins, or regular members if show_defaulters_publicly is enabled.
    """
    member = require_member(group_id, current_user, session)
    config, settings = get_association(group_id, session)

    if member.role != "ADMIN" and not settings.show_defaulters_publicly:
        raise HTTPException(status_code=403, detail="The defaulters ledger is private and only visible to the executive committee.")

    defaulters = session.exec(
        select(AssociationMemberDuesStanding).where(
            AssociationMemberDuesStanding.group_id == group_id,
            AssociationMemberDuesStanding.is_in_arrears == True
        )
    ).all()

    result = []
    for d in defaulters:
        u = session.exec(select(User).where(User.id == d.user_id)).first()
        result.append({
            "user_id": str(d.user_id),
            "full_name": u.full_name if u else "Member",
            "outstanding_arrears_balance": d.outstanding_arrears_balance,
            "consecutive_missed_cycles": d.consecutive_missed_cycles,
            "is_suspended": d.is_suspended,
            "next_due_date": d.next_due_date
        })

    return {
        "status": "success",
        "total_defaulters": len(result),
        "data": result
    }
