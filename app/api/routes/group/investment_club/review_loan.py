import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.investment_association import InvestmentClubLoan
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import ReviewLoanRequest
from .helpers import require_admin, get_club, now_ms as _now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/loans/{loan_id}/review", summary="Admin reviews and approves/rejects loan")
def review_loan(
    group_id: str,
    loan_id: str,
    request: ReviewLoanRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin approves or rejects a pending loan.
    If approved and disbursed, deducts principal from current_balance vault.
    """
    require_admin(group_id, current_user, session)
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

    if loan.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Loan is already {loan.status}.")

    new_status = request.status.upper()
    if new_status not in ["APPROVED", "REJECTED"]:
        raise HTTPException(status_code=400, detail="Status must be APPROVED or REJECTED.")

    if new_status == "APPROVED":
        if settings.current_balance < loan.principal_amount:
            raise HTTPException(status_code=400, detail="Insufficient club vault balance to disburse loan.")

        settings.current_balance -= loan.principal_amount
        settings.total_loans_disbursed += loan.principal_amount
        settings.active_loans_count += 1
        settings.updated_at = now_ms
        session.add(settings)

        loan.status = "DISBURSED"
        loan.disbursed_at = now_ms
        loan.approved_by = current_user.id
    else:
        loan.status = "REJECTED"

    loan.updated_at = now_ms
    session.add(loan)

    try:
        session.commit()
        session.refresh(loan)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error reviewing loan: {e}")
        raise HTTPException(status_code=500, detail="Database error reviewing loan.")

    borrower = session.exec(select(User).where(User.id == loan.user_id)).first()
    borrower_name = borrower.full_name if borrower else "Member"

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"ðŸ“¢ Loan Update: {borrower_name}'s loan was {loan.status}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": f"Loan {loan.status.lower()} successfully.",
        "data": loan.model_dump(mode="json")
    }

