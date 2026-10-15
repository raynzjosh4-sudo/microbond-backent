from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from typing import Optional
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.investment_association import InvestmentClubLoan
from .helpers import require_member

router = APIRouter()

@router.get("/{group_id}/loans", summary="List loans in the investment club")
def list_loans(
    group_id: str,
    status_filter: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    List loans in this club.
    Admins see all loans; regular members see only their own.
    """
    member = require_member(group_id, current_user, session)
    query = select(InvestmentClubLoan).where(InvestmentClubLoan.group_id == group_id)

    if member.role != "ADMIN":
        query = query.where(InvestmentClubLoan.user_id == current_user.id)

    if status_filter:
        query = query.where(InvestmentClubLoan.status == status_filter.upper())

    loans = session.exec(query).all()

    result = []
    for l in loans:
        u = session.exec(select(User).where(User.id == l.user_id)).first()
        result.append({
            "loan_id": str(l.id),
            "user_id": str(l.user_id),
            "borrower_name": u.full_name if u else "Member",
            "principal_amount": l.principal_amount,
            "interest_rate_pct": l.interest_rate_pct,
            "total_due_amount": l.total_due_amount,
            "amount_repaid": l.amount_repaid,
            "status": l.status,
            "due_date": l.due_date,
            "disbursed_at": l.disbursed_at,
            "settled_at": l.settled_at,
            "created_at": l.created_at
        })

    return {
        "status": "success",
        "count": len(result),
        "data": result
    }
