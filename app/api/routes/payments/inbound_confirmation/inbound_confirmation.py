import logging
from typing import Optional
from fastapi import APIRouter, Depends, Header, Request, status
from sqlmodel import Session

from app.core.database import get_session
from app.models.user.user import User
from app.services.finance.ledger import process_incoming_payment, broadcast_group_ring_update
from app.services.cloud_tasks import enqueue_push_task, enqueue_sms_task
from .schemas import InboundPaymentConfirmationPayload, InboundPaymentConfirmationResponse
from .helpers.verify_payment_signature import verify_payment_signature

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/inbound-confirmation",
    response_model=InboundPaymentConfirmationResponse,
    status_code=status.HTTP_200_OK,
    summary="Inbound Payment Gateway Confirmation",
    description="Secured endpoint invoked by the dedicated payment gateway project to confirm completed mobile money collections.",
)
async def inbound_payment_confirmation(
    request: Request,
    payload: InboundPaymentConfirmationPayload,
    session: Session = Depends(get_session),
    x_payment_signature: Optional[str] = Header(None, alias="X-Payment-Signature"),
    x_signature_sha256: Optional[str] = Header(None, alias="X-Signature-SHA256"),
):
    """
    Receives verified payment notifications from the dedicated external payment service.
    
    1. Validates HMAC signature against raw payload.
    2. Enforces ledger idempotency using unique external_reference_id.
    3. Atomically credits GroupWallet.pooled_funds and updates MemberObligation.
    4. Pushes real-time WebSocket ring status update to connected group members.
    5. Dispatches push/SMS receipt tasks asynchronously.
    """
    # 1. Verify HMAC signature
    raw_body = await request.body()
    signature_header = x_payment_signature or x_signature_sha256
    verify_payment_signature(raw_body, signature_header)

    logger.info(
        f"[PAYMENT_INBOUND] Received payment confirmation: Event={payload.event_id}, "
        f"Ref={payload.external_reference_id}, Status={payload.status}, Amount={payload.amount} UGX"
    )

    # 2. Handle failed transaction events
    if payload.status.upper() != "SUCCESS":
        logger.warning(
            f"[PAYMENT_INBOUND] Payment was not successful for ref {payload.external_reference_id}. "
            f"Reason: {payload.failure_reason}"
        )
        return InboundPaymentConfirmationResponse(
            status="FAILED",
            message=f"Payment marked as failed: {payload.failure_reason or 'unsuccessful'}",
            external_reference_id=payload.external_reference_id,
            ledger_entry_id=None,
            group_id=payload.group_id,
            amount_credited=0,
        )

    # 3. Process double-entry ledger entry atomically
    source_acc = payload.source_account or payload.provider
    ledger_entry = process_incoming_payment(
        session=session,
        group_id=payload.group_id,
        user_id=payload.user_id,
        amount=payload.amount,
        source_account=source_acc,
        external_ref=payload.external_reference_id,
        obligation_id=payload.obligation_id,
    )

    # 4. Handle idempotency (duplicate notification received)
    if not ledger_entry:
        logger.info(
            f"[PAYMENT_INBOUND] Duplicate payment event ignored for ref {payload.external_reference_id}"
        )
        return InboundPaymentConfirmationResponse(
            status="DUPLICATE",
            message="Payment already processed and settled in ledger",
            external_reference_id=payload.external_reference_id,
            ledger_entry_id=None,
            group_id=payload.group_id,
            amount_credited=0,
        )

    session.commit()
    session.refresh(ledger_entry)

    # 5. Fetch user details for real-time announcements & notification receipts
    user = session.get(User, payload.user_id)
    depositor_name = user.full_name if (user and user.full_name) else "A member"

    # 6. Real-time WebSocket Ring Status Broadcast
    try:
        await broadcast_group_ring_update(
            group_id=payload.group_id,
            depositor_name=depositor_name,
            amount=payload.amount,
        )
    except Exception as ex:
        logger.warning(f"[PAYMENT_INBOUND] WebSocket broadcast failed: {ex}")

    # 7. Asynchronous Notification Tasks (Push / SMS)
    if user and user.fcm_token:
        enqueue_push_task(
            token=user.fcm_token,
            title="Deposit Confirmed!",
            body=f"Your deposit of {payload.amount:,} UGX has been credited to group pool.",
            data={"group_id": payload.group_id, "type": "DEPOSIT_SUCCESS"},
        )

    user_phone = (user.phone_number if user else None) or payload.source_account
    if user_phone:
        enqueue_sms_task(
            phone_number=str(user_phone),
            message=f"Microbond: Deposit of {payload.amount:,} UGX credited to group pool. Ref: {payload.external_reference_id}",
        )

    return InboundPaymentConfirmationResponse(
        status="SUCCESS",
        message="Payment successfully credited to ledger and group pool",
        external_reference_id=payload.external_reference_id,
        ledger_entry_id=str(ledger_entry.id),
        group_id=payload.group_id,
        amount_credited=payload.amount,
    )
