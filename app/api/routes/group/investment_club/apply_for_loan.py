import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.investment_association import InvestmentClubLoan
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import ApplyLoanRequest
from .helpers import get_club, require_member, now_ms as _now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/loans/apply", summary="Member applies for an internal credit loan")
def apply_for_loan(
    group_id: str,
    request: ApplyLoanRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Member applies for a loan against the club's liquidity buffer.
    - Validates against max_borrowing_limit.
    - Computes interest due.
    """
    require_member(group_id, current_user, session)
    config, settings = get_club(group_id, session)
    now_ms = _now_ms()

    if request.principal_amount > settings.max_borrowing_limit:
        raise HTTPException(
            status_code=400,
            detail=f"Requested amount exceeds the club's maximum borrowing limit of {settings.max_borrowing_limit}."
        )

    interest_rate = settings.fixed_interest_rate_pct
    total_due = int(request.principal_amount * (1.0 + (interest_rate / 100.0)))

    loan = InvestmentClubLoan(
        group_id=group_id,
        user_id=current_user.id,
        principal_amount=request.principal_amount,
        interest_rate_pct=interest_rate,
        total_due_amount=total_due,
        amount_repaid=0,
        early_discount_applied=0,
        status="PENDING",
        guarantors_count=0,
        due_date=request.due_date,
        created_at=now_ms,
        updated_at=now_ms
    )
    session.add(loan)

    try:
        session.commit()
        session.refresh(loan)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error applying for loan: {e}")
        raise HTTPException(status_code=500, detail="Database error submitting loan application.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"ðŸ“‹ Loan Application: {current_user.full_name} requested a loan of {request.principal_amount}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Loan application submitted for committee review.",
        "data": loan.model_dump(mode="json")
    }

