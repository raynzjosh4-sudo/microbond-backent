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
from app.core.rate_limit import RateLimiter
from .schemas import SubmitClaimRequest
from .helpers import get_welfare_fund, require_member, now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/{group_id}/submit-claim",
    summary="Member submits an emergency claim",
    dependencies=[Depends(RateLimiter(times=3, seconds=60, fail_open=True, key_prefix="claim"))]
)
def submit_claim(
    group_id: str,
    request: SubmitClaimRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Active member submits an emergency claim against the fund.
    - Validates waiting period.
    - Validates documentary evidence if required.
    - Validates per-incident claim limit.
    - Validates reserve fund coverage.
    - Opens a claim poll for committee/group vote or admin approval.
    """
    member = require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_welfare_fund(group_id, session)
    current_time_ms = now_ms()

    if not settings.is_active:
        raise HTTPException(status_code=400, detail="This Welfare Fund is currently paused or inactive.")

    # 1. Waiting period check
    waiting_period_ms = config.waiting_period_days * 86400 * 1000
    if (member.joined_at + waiting_period_ms) > current_time_ms:
        remaining_days = max(1, int(((member.joined_at + waiting_period_ms) - current_time_ms) / (86400 * 1000)))
        raise HTTPException(
            status_code=400,
            detail=f"Waiting period not fulfilled. You must wait {remaining_days} more day(s) before submitting claims."
        )

    # 2. Documentary evidence check
    if config.requires_documentary_evidence and not request.evidence_reference:
        raise HTTPException(
            status_code=400,
            detail="Documentary evidence (e.g. medical bill or police report reference) is required to submit a claim."
        )

    # 3. Max claim amount check
    if request.amount > config.max_claim_amount_per_incident:
        raise HTTPException(
            status_code=400,
            detail=f"Claim amount exceeds the maximum incident limit of {config.max_claim_amount_per_incident} {group.currency}."
        )

    # 4. Solvency check
    available_reserve = settings.current_balance - settings.minimum_reserve_balance
    if available_reserve < request.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient available fund balance. The fund currently has {max(0, available_reserve)} {group.currency} available for claims above minimum reserve."
        )

    # 5. Create claim poll
    expires_at = current_time_ms + (settings.approval_timeout_hours * 3600 * 1000)
    poll_id = uuid.uuid4()
    poll = GroupPoll(
        id=poll_id,
        group_id=group_id,
        creator_id=current_user.id,
        question=f"Emergency Claim: {current_user.full_name} requested {request.amount} {group.currency} for {request.emergency_type}",
        options=json.dumps(["APPROVE", "REJECT"]),
        poll_type="CLAIM_APPROVAL",
        status="OPEN",
        expires_at=expires_at,
        created_at=current_time_ms
    )
    session.add(poll)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error submitting claim: {e}")
        raise HTTPException(status_code=500, detail="Database error submitting claim.")

    # 6. Broadcast notification to group chat
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=(
            f"🚨 New Claim Submitted: {current_user.full_name} requested {request.amount} {group.currency} "
            f"for '{request.emergency_type}'. Please review and vote before the approval timeout."
        ),
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Emergency claim submitted successfully and voting poll has been created.",
        "data": {
            "poll_id": str(poll_id),
            "amount": request.amount,
            "emergency_type": request.emergency_type,
            "description": request.description,
            "evidence_reference": request.evidence_reference,
            "expires_at": expires_at
        }
    }
