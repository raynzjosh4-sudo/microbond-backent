import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.investment_association import InvestmentClubLoan
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import RepayLoanRequest
from .helpers import get_club, require_member, now_ms as _now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/loans/{loan_id}/repay", summary="Borrower repays loan capital or interest")
def repay_loan(
    group_id: str,
    loan_id: str,
    request: RepayLoanRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Borrower repays principal and interest.
    Funds return to the club's current_balance vault.
    If repaid early, calculates and applies early_repayment_discount_pct.
    """
    require_member(group_id, current_user, session)
    config, settings = get_club(group_id, session)
    now_ms = _now_ms()

    try:
        loan_uuid = uuid.UUID(loan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid loan_id format.")

    loan = session.exec(
        select(InvestmentClubLoan).where(
            InvestmentClubLoan.id == loan_uuid,
            InvestmentClubLoan.group_id == group_id
        )
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found.")

    if loan.status not in ["APPROVED", "DISBURSED"]:
        raise HTTPException(status_code=400, detail=f"Cannot repay loan in {loan.status} status.")

    remaining_due = loan.total_due_amount - loan.amount_repaid
    payment_amount = min(request.amount, remaining_due)

    # Check for early repayment discount if paying off in full ahead of deadline
    if now_ms < loan.due_date and (loan.amount_repaid + payment_amount >= loan.total_due_amount):
        discount = int(loan.principal_amount * (settings.early_repayment_discount_pct / 100.0))
        loan.early_discount_applied = discount
        payment_amount = max(0, payment_amount - discount)

    loan.amount_repaid += payment_amount
    settings.current_balance += payment_amount
    settings.updated_at = now_ms

    if loan.amount_repaid + loan.early_discount_applied >= loan.total_due_amount:
        loan.status = "REPAID"
        loan.settled_at = now_ms
        if settings.active_loans_count > 0:
            settings.active_loans_count -= 1

    loan.updated_at = now_ms
    session.add(loan)
    session.add(settings)

    try:
        session.commit()
        session.refresh(loan)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error repaying loan: {e}")
        raise HTTPException(status_code=500, detail="Database error recording repayment.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"ðŸ’³ Loan Repayment: {current_user.full_name} repaid {payment_amount}. Remaining: {max(0, loan.total_due_amount - loan.amount_repaid - loan.early_discount_applied)}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Loan repayment recorded successfully.",
        "data": {
            "loan_id": str(loan.id),
            "amount_paid": payment_amount,
            "early_discount_applied": loan.early_discount_applied,
            "status": loan.status,
            "remaining_due": max(0, loan.total_due_amount - loan.amount_repaid - loan.early_discount_applied)
        }
    }

