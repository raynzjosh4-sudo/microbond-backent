import uuid
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group
from app.models.user.user import User
from app.models.group.chat import GroupPoll
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import RequestDisbursementRequest
from .helpers import get_event_committee, require_admin, now_ms as _now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/request-disbursement", summary="Admin requests vendor disbursement or payment")
def request_disbursement(
    group_id: str,
    request: RequestDisbursementRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin initiates payout to vendor or treasurer:
    - Validates fund balance.
    - Validates invoice requirement if required by config.
    - If COMMITTEE_CONSENSUS: creates an approval poll for the committee.
    - If CHAIRMAN_ONLY: executes payment directly.
    """
    require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_event_committee(group_id, session)
    now_ms = _now_ms()

    # 1. Balance check
    if settings.current_balance < request.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Balance is {settings.current_balance} {group.currency}, requested {request.amount} {group.currency}."
        )

    # 2. Invoice requirement check
    if config.require_invoice_upload and not request.invoice_reference:
        raise HTTPException(
            status_code=400,
            detail="Invoice photo reference is required before disbursement can be approved."
        )

    # 3. Partial disbursement check before deadline
    if now_ms < config.collection_deadline and not settings.allow_partial_disbursements:
        raise HTTPException(
            status_code=400,
            detail="Partial disbursements before collection deadline are not allowed by current settings."
        )

    # 4. Committee Consensus Policy -> Poll
    if config.spending_signoff_policy == "COMMITTEE_CONSENSUS":
        poll_id = uuid.uuid4()
        poll = GroupPoll(
            id=poll_id,
            group_id=group_id,
            creator_id=current_user.id,
            question=f"Disbursement Approval: {request.amount} {group.currency} to {request.recipient_name} for '{request.reason}'",
            options=json.dumps(["APPROVE", "REJECT"]),
            poll_type="DISBURSEMENT_APPROVAL",
            status="OPEN",
            expires_at=now_ms + (48 * 3600 * 1000),
            created_at=now_ms
        )
        session.add(poll)
        session.commit()

        broadcast_system_message_sync(
            group_id=group_id,
            message_text=(
                f"📋 Vendor Payment Signoff: {current_user.full_name} requested {request.amount} {group.currency} "
                f"for '{request.recipient_name}' ({request.reason}). Please vote to approve."
            ),
            message_type="SYSTEM_EVENT",
            sender_id=str(current_user.id),
            session=session,
            background_tasks=background_tasks
        )

        return {
            "status": "pending_approval",
            "message": "Disbursement submitted for committee signoff.",
            "data": {
                "poll_id": str(poll_id),
                "amount": request.amount,
                "recipient_name": request.recipient_name,
                "reason": request.reason
            }
        }

    # 5. Chairman Only Policy -> Direct Execution
    settings.current_balance = max(0, settings.current_balance - request.amount)
    settings.total_disbursed += request.amount
    settings.updated_at = now_ms
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error executing disbursement: {e}")
        raise HTTPException(status_code=500, detail="Database error executing disbursement.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"💸 Payment Disbursed: {request.amount} {group.currency} paid to {request.recipient_name} for '{request.reason}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Payment disbursed successfully.",
        "data": {
            "amount_paid": request.amount,
            "recipient_name": request.recipient_name,
            "remaining_balance": settings.current_balance,
            "total_disbursed": settings.total_disbursed
        }
    }
