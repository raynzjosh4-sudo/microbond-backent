import time
import secrets
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupFinancialSettings
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.finance import MemberObligation, GroupPenalty
from app.models.user.security_email import UserSecurityEmail
from app.communications.sms_service import SMS_FEE_UGX, send_deposit_receipt_sms

router = APIRouter(prefix="/api/v1/groups", tags=["Group Deposit Pipeline"])

# --- Schemas ---

class DepositInfoResponse(BaseModel):
    group_id: str
    group_name: str
    required_base_amount: int
    accumulated_penalties: int
    amount_already_paid: int
    total_due: int
    allow_partial_pay: bool
    allow_overpay: bool
    currency: str = "UGX"

class DepositQuoteRequest(BaseModel):
    entered_amount: int = Field(..., gt=0, description="Amount user typed in UGX (Integer)")

class DepositQuoteResponse(BaseModel):
    group_id: str
    deposit_amount: int
    transaction_fee: int
    sms_fee_ugx: int = 0          # Non-zero only if member has SMS opt-in
    total_to_charge: int
    quote_token: str
    validation_status: str = "VALIDATED"
    currency: str = "UGX"
    sms_fee_notice: Optional[str] = None

# --- Endpoints ---

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


def trigger_post_deposit_notifications(
    group_id: str,
    user_id,
    amount_deposited: int,
    session: Session
):
    """
    Called by the payment webhook/confirmation handler after a successful deposit.
    - Sends SMS receipt if member is opted in.
    - Sends email receipt if member has a verified security email.
    - Resets pending_sms_fee_ugx to 0 (it was already billed into the quote).
    """
    try:
        user = session.exec(select(User).where(User.id == user_id)).first()
        group = session.exec(select(Group).where(Group.group_id == group_id)).first()
        membership = session.exec(
            select(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.user_id == user_id
            )
        ).first()

        if not user or not group or not membership:
            return

        member_name = user.full_name or "Member"
        group_name = group.name
        currency = group.currency or "UGX"

        # 1. SMS receipt (if opted in)
        if membership.sms_reminders_opted_in and user.phone_number:
            send_deposit_receipt_sms(
                phone_number=user.phone_number,
                member_name=member_name,
                group_name=group_name,
                amount_deposited=amount_deposited,
                sms_fee=SMS_FEE_UGX,
                currency=currency
            )
            # Reset pending fee counter
            membership.pending_sms_fee_ugx = 0
            session.add(membership)
            session.commit()

        # 2. Email receipt (if verified security email exists)
        security_email_row = session.exec(
            select(UserSecurityEmail).where(
                UserSecurityEmail.user_id == user_id,
                UserSecurityEmail.is_verified == True
            )
        ).first()

        if security_email_row and membership.sms_reminders_opted_in:
            try:
                import asyncio
                from app.services.communication.email_service import EmailNotificationService
                from app.services.communication.email_templates import build_deposit_receipt_email

                html_body = build_deposit_receipt_email(
                    member_name=member_name,
                    group_name=group_name,
                    amount_deposited=amount_deposited,
                    sms_fee_ugx=SMS_FEE_UGX,
                    currency=currency
                )
                asyncio.run(EmailNotificationService._dispatch(
                    recipient_email=security_email_row.email,
                    subject=f"Deposit Received — {group_name}",
                    html_body=html_body
                ))
            except Exception as email_err:
                import logging
                logging.getLogger(__name__).warning(f"[DEPOSIT EMAIL] Failed: {email_err}")

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[POST_DEPOSIT_NOTIFY] Error: {e}")

