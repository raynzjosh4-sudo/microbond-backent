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

    from app.utils.time.now_epoch_ms import now_epoch_ms
    now_ms = now_epoch_ms()

    # Rule: Group must not be forming
    if group.status in ["FORMING", "PENDING"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Group is still forming ({group.member_count}/{group.max_members or '?'} members). Deposits open once the circle is full."
        )

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
            if rot.group_start_time and now_ms < rot.group_start_time and not rot.is_payout_order_locked:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This group schedule has not started yet. No deposits can be accepted until the start time."
                )
            base_contribution = int(rot.contribution_amount)
            allow_partial = rot.allow_partial_payments
            allow_overpay = rot.allow_advance_deposits
            current_cycle = rot.current_cycle
    elif group.type == "GOAL_SAVINGS":
        from app.models.group.target_savings.target_savings_group_details import TargetSavingsGroupDetails
        target = session.exec(
            select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
        ).first()
        if target:
            base_contribution = int(target.contribution_amount) if target.contribution_amount else int(target.target_amount or 0)
            allow_partial = True
            allow_overpay = True

    # Fetch active MemberObligation for current cycle
    obligation = session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == group_id,
            MemberObligation.user_id == current_user.id,
            MemberObligation.cycle_number == current_cycle
        )
    ).first()

    original_amount_due = base_contribution
    amount_paid = 0
    if obligation:
        # If no deposit was made yet and the base contribution changed in settings/DB, sync it
        if obligation.amount_paid == 0 and base_contribution > 0 and obligation.amount_due != base_contribution:
            obligation.amount_due = base_contribution
            session.add(obligation)
            session.commit()
        original_amount_due = int(obligation.amount_due)  # The full original obligation (never changes)
        amount_paid = int(obligation.amount_paid)         # How much has been paid so far

    # Calculate unpaid penalties
    penalties = session.exec(
        select(func.sum(GroupPenalty.penalty_amount)).where(
            GroupPenalty.group_id == group_id,
            GroupPenalty.user_id == current_user.id,
            GroupPenalty.is_paid == False
        )
    ).one() or 0
    penalties = int(penalties)

    # total_due = what the user still owes (remaining balance after any partial/full payments)
    total_due = max(0, (original_amount_due + penalties) - amount_paid)

    # Calculate minimum partial payment threshold
    if allow_partial:
        # Standard mobile money minimum deposit floor: 1,000 UGX (or total_due if less)
        minimum_partial_amount = min(1000, total_due) if total_due > 0 else 1000
    else:
        # Partial disabled: user must enter full total_due
        minimum_partial_amount = total_due

    maximum_deposit_amount = None if allow_overpay else total_due

    return DepositInfoResponse(
        group_id=group_id,
        group_name=group.name,
        group_type=group.type,
        required_base_amount=original_amount_due,  # The original full contribution amount (informational)
        expected_amount=total_due,                  # What the user actually needs to pay NOW (0 if fully paid)
        accumulated_penalties=penalties,
        amount_already_paid=amount_paid,
        total_due=total_due,                        # True remaining balance
        remaining_due=total_due,
        minimum_partial_amount=minimum_partial_amount,
        maximum_deposit_amount=maximum_deposit_amount,
        allow_partial_pay=allow_partial,
        allow_overpay=allow_overpay,
        cycle_number=current_cycle,
        due_date=obligation.due_date if obligation else None,
        currency=group.currency or "UGX",
        member_prepaid_balance=int(membership.credit_balance_ugx or 0)
    )

