import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.chat import GroupPoll
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.core.rate_limit import RateLimiter
from .schemas import RequestSpendBody
from .helpers import get_wallet, require_member, now_ms

router = APIRouter()

@router.post(
    "/{group_id}/request-spend",
    summary="Request or initiate a spend from shared funds",
    dependencies=[Depends(RateLimiter(times=5, seconds=60, fail_open=True, key_prefix="spend"))]
)
def request_spend(
    group_id: str,
    request: RequestSpendBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Requests a spend from the shared wallet.
    - If spend amount <= auto_approve_threshold and user authorized: instantly approved.
    - If spend amount > auto_approve_threshold: creates a SPEND_APPROVAL voting poll for members.
    """
    membership = require_member(group_id, current_user, session)
    config, op_settings = get_wallet(group_id, session)

    if not op_settings.is_active:
        raise HTTPException(status_code=400, detail="This shared wallet is currently paused or inactive.")

    # 1. Check spending policy permission
    if config.spending_signoff_policy == "ADMIN_ONLY" and membership.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can initiate spending in this wallet.")

    # 2. Check minimum balance floor
    spendable = op_settings.current_balance - op_settings.minimum_balance_floor
    if request.amount > spendable:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient spendable balance. Current balance is {op_settings.current_balance:,}, "
                f"reserve floor is {op_settings.minimum_balance_floor:,}. Max spendable is {spendable:,}."
            )
        )

    # 3. Check per-transaction cap
    if op_settings.per_transaction_cap and request.amount > op_settings.per_transaction_cap:
        raise HTTPException(
            status_code=400,
            detail=f"Amount exceeds per-transaction cap of {op_settings.per_transaction_cap:,}."
        )

    # 4. Check recipient type allowance
    try:
        allowed = json.loads(op_settings.allowed_disbursement_types)
    except Exception:
        allowed = ["MEMBER_ACCOUNTS", "EXTERNAL_PAYEES"]
    if request.recipient_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Disbursements to {request.recipient_type} are not allowed. Allowed types: {allowed}."
        )

    current_time_ms = now_ms()

    # Case A: Auto-Approve (amount <= threshold)
    if request.amount <= op_settings.auto_approve_threshold:
        op_settings.current_balance -= request.amount
        op_settings.total_spent += request.amount
        op_settings.updated_at = current_time_ms
        session.add(op_settings)
        session.commit()

        broadcast_system_message_sync(
            group_id=group_id,
            message_text=(
                f"{current_user.full_name} spent {request.amount:,} to {request.recipient_name} "
                f"({request.recipient_identifier}). Memo: {request.reason}."
            ),
            message_type="SYSTEM_EVENT",
            sender_id=str(current_user.id),
            session=session,
            background_tasks=background_tasks
        )

        return {
            "status": "success",
            "message": "Spend auto-approved and executed.",
            "data": {
                "amount": request.amount,
                "recipient_name": request.recipient_name,
                "recipient_identifier": request.recipient_identifier,
                "remaining_balance": op_settings.current_balance,
                "auto_approved": True
            }
        }

    # Case B: Requires member approval vote
    timeout_ms = op_settings.approval_timeout_hours * 3600 * 1000
    expires_at = current_time_ms + timeout_ms

    poll = GroupPoll(
        group_id=group_id,
        creator_id=current_user.id,
        question=f"Approve spend of {request.amount:,} to {request.recipient_name}? Reason: {request.reason}",
        options=json.dumps(["Approve Spend", "Reject Spend"]),
        poll_type="SPEND_APPROVAL",
        status="OPEN",
        expires_at=expires_at,
        created_at=current_time_ms
    )
    session.add(poll)
    session.commit()
    session.refresh(poll)

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=json.dumps({
            "poll_id": str(poll.id),
            "question": poll.question,
            "options": ["Approve Spend", "Reject Spend"],
            "amount": request.amount,
            "recipient_name": request.recipient_name,
            "expires_at": expires_at,
            "signoff_policy": config.spending_signoff_policy
        }),
        message_type="VOTE",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "pending_approval",
        "message": f"Spend requires approval under {config.spending_signoff_policy} policy. Voting poll created.",
        "data": {
            "poll_id": str(poll.id),
            "amount": request.amount,
            "recipient_name": request.recipient_name,
            "expires_at": expires_at,
            "signoff_policy": config.spending_signoff_policy
        }
    }
