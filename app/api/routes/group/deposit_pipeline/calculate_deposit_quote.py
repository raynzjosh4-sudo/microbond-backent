import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.communications.sms_service import SMS_FEE_UGX
from .schemas import DepositQuoteRequest, DepositQuoteResponse
from .get_deposit_info import get_deposit_info

router = APIRouter()

@router.post(
    "/{group_id}/deposit-quote",
    response_model=DepositQuoteResponse,
    summary="Layer 2: Validate Amount & Calculate Mobile Money Fees",
    description="Validates entered amount against partial/overpay rules and calculates mobile money gateway fee. Includes 50 UGX SMS fee if member opted in."
)
def calculate_deposit_quote(
    group_id: str,
    payload: DepositQuoteRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # Fetch deposit info rules
    info = get_deposit_info(group_id=group_id, current_user=current_user, session=session)

    entered = payload.entered_amount

    # Rule 1: Partial payment check
    if not info.allow_partial_pay and entered < info.total_due and info.total_due > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Partial payments are disabled for this group. You must pay the full required amount of {info.total_due:,} UGX."
        )

    # Rule 2: Overpay check
    if not info.allow_overpay and info.total_due > 0 and entered > info.total_due:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Overpayments are disabled for this group. Maximum allowed deposit is {info.total_due:,} UGX."
        )

    # Rule 3: Mobile Money Tiered Fee Calculation (1.5% with 200 UGX min, 5000 UGX max)
    raw_fee = int(entered * 0.015)
    tx_fee = max(200, min(5000, raw_fee))

    # Rule 4: SMS fee — only charged if member opted in to SMS reminders for this group
    sms_fee = 0
    sms_fee_notice = None
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if membership and membership.sms_reminders_opted_in:
        sms_fee = SMS_FEE_UGX
        sms_fee_notice = (
            f"A {info.currency} {SMS_FEE_UGX} SMS notification fee is included "
            f"because you have enabled SMS reminders for this group."
        )
        # Accumulate fee on membership so it deducts on payment confirmation
        membership.pending_sms_fee_ugx = (membership.pending_sms_fee_ugx or 0) + SMS_FEE_UGX
        session.add(membership)
        session.commit()

    total_charge = entered + tx_fee + sms_fee

    # Generate secure 15-minute quote token
    token = f"quote_{secrets.token_urlsafe(16)}"

    return DepositQuoteResponse(
        group_id=group_id,
        deposit_amount=entered,
        transaction_fee=tx_fee,
        sms_fee_ugx=sms_fee,
        total_to_charge=total_charge,
        quote_token=token,
        validation_status="VALIDATED",
        currency=info.currency,
        sms_fee_notice=sms_fee_notice
    )
