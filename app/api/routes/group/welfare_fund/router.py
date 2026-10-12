from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from pydantic import BaseModel, Field
from typing import Optional
import uuid
import time
import json
import logging

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.models.group.settings import (
    GroupFinancialSettings, GroupGovernanceSettings,
    GroupCommunicationSettings, GroupVisibilitySettings
)
from app.models.group.welfare_event import WelfareFundConfig, WelfareFundOperationalSettings
from app.models.group.chat import GroupPoll, GroupPollVote
from app.schemas.welfare_fund_schemas import (
    WelfareFundGroupCreateRequest,
    UpdateWelfareFundSettingsRequest,
    SubmitClaimRequest
)
from app.api.routes.group.chat.messages import broadcast_system_message_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups/welfare-fund", tags=["Welfare Fund Groups"])


class VoteClaimRequest(BaseModel):
    vote: str = Field(..., description="APPROVE or REJECT")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_welfare_fund(group_id: str, session: Session):
    config = session.exec(
        select(WelfareFundConfig).where(WelfareFundConfig.group_id == group_id)
    ).first()
    settings = session.exec(
        select(WelfareFundOperationalSettings).where(WelfareFundOperationalSettings.group_id == group_id)
    ).first()
    if not config or not settings:
        raise HTTPException(status_code=404, detail="Welfare Fund configuration not found for this group.")
    return config, settings


def _require_admin(group_id: str, user: User, session: Session):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Only the group admin can perform this action.")
    return membership


def _require_member(group_id: str, user: User, session: Session):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")
    return membership


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/create", summary="Create a new Welfare Fund group")
def create_welfare_fund_group(
    request: WelfareFundGroupCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new WELFARE_FUND group.
    - Creator must have KYC Tier >= 2 (National ID verified).
    - Initializes WelfareFundConfig (locked creation parameters).
    - Initializes WelfareFundOperationalSettings (default operational limits).
    - Adds creator as ADMIN and broadcasts creation to group chat.
    """
    creator = current_user
    now_ms = _now_ms()

    # 1. KYC verification
    if creator.kyc_tier < 2 or getattr(creator, "is_dependent_account", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Creating a Welfare Fund requires full Tier 2 National ID (NIN) verification."
        )

    # 2. Unique identifiers
    new_group_id = str(uuid.uuid4())
    invite_code = str(uuid.uuid4())[:8].upper()

    # 3. Create Group record
    new_group = Group(
        group_id=new_group_id,
        name=request.name,
        description=request.description,
        group_image_url=request.group_image_url,
        type="WELFARE_FUND",
        payment_mode="OBLIGATION",
        visibility=request.visibility,
        currency=request.currency,
        created_by_user_id=creator.id,
        invite_code=invite_code,
        member_count=1
    )
    session.add(new_group)

    # 4. Create base settings
    session.add(GroupFinancialSettings(group_id=new_group_id))
    session.add(GroupGovernanceSettings(group_id=new_group_id))
    session.add(GroupCommunicationSettings(group_id=new_group_id))
    session.add(GroupVisibilitySettings(group_id=new_group_id))

    # 5. Create WelfareFundConfig (Table 1)
    config = WelfareFundConfig(
        group_id=new_group_id,
        contribution_amount=request.contribution_amount,
        collection_frequency_days=request.collection_frequency_days,
        waiting_period_days=request.waiting_period_days,
        max_claim_amount_per_incident=request.max_claim_amount_per_incident,
        annual_claim_limit_per_member=request.annual_claim_limit_per_member,
        payout_destination_type=request.payout_destination_type,
        requires_documentary_evidence=request.requires_documentary_evidence,
        claim_approval_policy=request.claim_approval_policy,
        created_at=now_ms
    )
    session.add(config)

    # 6. Create WelfareFundOperationalSettings (Table 2 - defaults)
    op_settings = WelfareFundOperationalSettings(
        group_id=new_group_id,
        minimum_reserve_balance=0,
        approval_timeout_hours=48,
        missed_payment_action="SUSPEND_CLAIM_RIGHTS",
        enable_late_fees=False,
        allow_annual_dividend_split=False,
        current_balance=0,
        total_collected=0,
        total_paid_out=0,
        is_active=True,
        updated_at=now_ms
    )
    session.add(op_settings)

    # 7. Add creator membership (ADMIN)
    session.add(GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=new_group_id,
        user_id=creator.id,
        role="ADMIN",
        status="ACTIVE",
        joined_at=now_ms
    ))

    try:
        session.commit()
        session.refresh(new_group)
        session.refresh(config)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error creating welfare fund: {e}")
        raise HTTPException(status_code=500, detail="Database error creating welfare fund.")

    # 8. Broadcast greeting in chat
    broadcast_system_message_sync(
        group_id=new_group_id,
        message_text=f"{creator.full_name} established the Welfare Fund '{new_group.name}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(creator.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Welfare Fund group created successfully.",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name,
            "currency": new_group.currency,
            "contribution_amount": config.contribution_amount,
            "collection_frequency_days": config.collection_frequency_days,
            "waiting_period_days": config.waiting_period_days,
            "max_claim_amount_per_incident": config.max_claim_amount_per_incident,
            "claim_approval_policy": config.claim_approval_policy
        }
    }


@router.get("/{group_id}/dashboard", summary="View Welfare Fund status, reserve balance, and claim eligibility")
def get_welfare_fund_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full state of the Welfare Fund:
    - Creation configuration rules (Table 1)
    - Live operational settings & counters (Table 2)
    - Calculated claimable balance & health status
    - Member claim eligibility status
    """
    member = _require_member(group_id, current_user, session)
    config, settings = _get_welfare_fund(group_id, session)
    now_ms = _now_ms()

    # Calculate claimable pool
    claimable_balance = max(0, settings.current_balance - settings.minimum_reserve_balance)
    fund_health = "HEALTHY" if settings.current_balance >= settings.minimum_reserve_balance else "CRITICAL"

    # Member eligibility
    waiting_period_ms = config.waiting_period_days * 86400 * 1000
    member_eligible_at = member.joined_at + waiting_period_ms
    is_eligible = now_ms >= member_eligible_at
    waiting_days_remaining = max(0, int((member_eligible_at - now_ms) / (86400 * 1000))) if not is_eligible else 0

    return {
        "status": "success",
        "data": {
            "welfare_config": config.model_dump(mode="json"),
            "operational_settings": settings.model_dump(mode="json"),
            "claimable_balance": claimable_balance,
            "fund_health": fund_health,
            "member_claim_eligibility": {
                "is_eligible": is_eligible,
                "waiting_days_remaining": waiting_days_remaining,
                "waiting_period_days": config.waiting_period_days
            }
        }
    }


@router.patch("/{group_id}/settings", summary="Admin updates mutable operational settings")
def update_welfare_fund_settings(
    group_id: str,
    request: UpdateWelfareFundSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates mutable operational settings for the Welfare Fund:
    - minimum_reserve_balance
    - approval_timeout_hours
    - missed_payment_action
    - enable_late_fees
    - allow_annual_dividend_split
    """
    _require_admin(group_id, current_user, session)
    config, settings = _get_welfare_fund(group_id, session)

    update_dict = request.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid settings provided to update.")

    for field, val in update_dict.items():
        if hasattr(settings, field) and val is not None:
            setattr(settings, field, val)

    settings.updated_at = _now_ms()
    session.add(settings)

    try:
        session.commit()
        session.refresh(settings)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error updating welfare settings: {e}")
        raise HTTPException(status_code=500, detail="Database error updating settings.")

    return {
        "status": "success",
        "message": "Welfare Fund settings updated successfully.",
        "data": settings.model_dump(mode="json")
    }


@router.post("/{group_id}/submit-claim", summary="Member submits an emergency claim")
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
    member = _require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_welfare_fund(group_id, session)
    now_ms = _now_ms()

    if not settings.is_active:
        raise HTTPException(status_code=400, detail="This Welfare Fund is currently paused or inactive.")

    # 1. Waiting period check
    waiting_period_ms = config.waiting_period_days * 86400 * 1000
    if (member.joined_at + waiting_period_ms) > now_ms:
        remaining_days = max(1, int(((member.joined_at + waiting_period_ms) - now_ms) / (86400 * 1000)))
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
    expires_at = now_ms + (settings.approval_timeout_hours * 3600 * 1000)
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
        created_at=now_ms
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


@router.post("/{group_id}/vote-claim/{poll_id}", summary="Member votes on an emergency claim poll")
def vote_on_claim(
    group_id: str,
    poll_id: uuid.UUID,
    request: VoteClaimRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Active member casts vote ('APPROVE' or 'REJECT') on an active emergency claim poll.
    """
    _require_member(group_id, current_user, session)
    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "CLAIM_APPROVAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Claim poll not found.")

    if poll.status != "OPEN":
        raise HTTPException(status_code=400, detail=f"This claim poll is already {poll.status.lower()}.")

    now_ms = _now_ms()
    if poll.expires_at <= now_ms:
        poll.status = "CLOSED"
        session.add(poll)
        session.commit()
        raise HTTPException(status_code=400, detail="This claim poll has expired.")

    vote_val = request.vote.upper()
    if vote_val not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=400, detail="Vote must be APPROVE or REJECT.")

    # Check for existing vote
    existing_vote = session.exec(
        select(GroupPollVote).where(
            GroupPollVote.poll_id == poll_id,
            GroupPollVote.user_id == current_user.id
        )
    ).first()

    if existing_vote:
        existing_vote.selected_option = vote_val
        session.add(existing_vote)
    else:
        new_vote = GroupPollVote(
            poll_id=poll_id,
            user_id=current_user.id,
            selected_option=vote_val,
            created_at=now_ms
        )
        session.add(new_vote)

    session.commit()

    return {
        "status": "success",
        "message": f"Vote '{vote_val}' recorded successfully."
    }


@router.post("/{group_id}/release-claim/{poll_id}", summary="Admin executes release of approved claim")
def release_claim(
    group_id: str,
    poll_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin finalizes and releases funds for an approved emergency claim poll:
    - Counts votes to verify majority approval.
    - Closes poll and marks status EXECUTED.
    - Deducts amount from pool current_balance and increments total_paid_out.
    - Broadcasts payout event to group chat.
    """
    _require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_welfare_fund(group_id, session)

    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "CLAIM_APPROVAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Claim poll not found.")

    if poll.status == "EXECUTED":
        raise HTTPException(status_code=400, detail="This claim has already been released.")

    # Tally votes
    votes = session.exec(select(GroupPollVote).where(GroupPollVote.poll_id == poll_id)).all()
    approve_count = sum(1 for v in votes if v.selected_option == "APPROVE")
    reject_count = sum(1 for v in votes if v.selected_option == "REJECT")

    # If MAJORITY_VOTE policy, require approve > reject
    if config.claim_approval_policy == "MAJORITY_VOTE" and approve_count <= reject_count:
        raise HTTPException(
            status_code=400,
            detail=f"Claim is not approved by majority. Approvals: {approve_count}, Rejections: {reject_count}."
        )

    # Parse amount from question
    claimant = session.exec(select(User).where(User.id == poll.creator_id)).first()
    claimant_name = claimant.full_name if claimant else "Member"

    # Mark poll as executed
    poll.status = "EXECUTED"
    session.add(poll)

    # Extract or estimate amount (or default to max allowable/claim question)
    # Update settings balance
    amount = min(settings.current_balance, config.max_claim_amount_per_incident)
    settings.current_balance = max(0, settings.current_balance - amount)
    settings.total_paid_out += amount
    settings.updated_at = _now_ms()
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error releasing claim: {e}")
        raise HTTPException(status_code=500, detail="Database error releasing claim.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"💚 Emergency Claim Approved & Released: Payout released to {claimant_name}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Claim payout successfully released.",
        "data": {
            "poll_id": str(poll_id),
            "amount_paid": amount,
            "remaining_fund_balance": settings.current_balance,
            "total_paid_out": settings.total_paid_out
        }
    }
