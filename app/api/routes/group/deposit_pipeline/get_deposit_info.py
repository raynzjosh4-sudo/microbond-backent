from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.finance import MemberObligation, GroupPenalty
from .schemas import DepositInfoResponse

router = APIRouter()

@router.get(
    "/{group_id}/deposit-info",
    response_model=DepositInfoResponse,
    summary="Layer 1: Fetch Group Deposit Rules & User Arrears",
    description="Called when opening the deposit screen. Evaluates group financial rules, cycle obligations, and accumulated penalties."
)
def get_deposit_info(
    group_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this group."
        )

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    # Defaults
    allow_partial = False
    allow_overpay = True
    base_contribution = 0
    current_cycle = 1

    # Check Rotating Details if applicable
    if group.type == "MERRY_GO_ROUND":
        rot = session.exec(
            select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
        ).first()
        if rot:
            base_contribution = int(rot.contribution_amount)
            allow_partial = rot.allow_partial_payments
            allow_overpay = rot.allow_advance_deposits
            current_cycle = rot.current_cycle

    # Fetch active MemberObligation for current cycle
    obligation = session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == group_id,
            MemberObligation.user_id == current_user.id,
            MemberObligation.cycle_number == current_cycle
        )
    ).first()

    amount_due = base_contribution
    amount_paid = 0
    if obligation:
        amount_due = obligation.amount_due
        amount_paid = obligation.amount_paid

    # Calculate unpaid penalties
    penalties = session.exec(
        select(func.sum(GroupPenalty.penalty_amount)).where(
            GroupPenalty.group_id == group_id,
            GroupPenalty.user_id == current_user.id,
            GroupPenalty.is_paid == False
        )
    ).one() or 0

    total_due = max(0, (amount_due + penalties) - amount_paid)

    return DepositInfoResponse(
        group_id=group_id,
        group_name=group.name,
        required_base_amount=amount_due,
        accumulated_penalties=penalties,
        amount_already_paid=amount_paid,
        total_due=total_due,
        allow_partial_pay=allow_partial,
        allow_overpay=allow_overpay,
        currency=group.currency or "UGX"
    )
