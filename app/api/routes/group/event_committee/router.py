from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
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
from app.models.group.welfare_event import EventCommitteeConfig, EventCommitteeOperationalSettings
from app.models.group.chat import GroupPoll
from app.schemas.event_committee_schemas import (
    EventCommitteeGroupCreateRequest,
    UpdateEventCommitteeSettingsRequest,
    SubmitPledgeRequest,
    RequestDisbursementRequest
)
from app.api.routes.group.chat.messages import broadcast_system_message_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups/event-committee", tags=["Event Committee Groups"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_event_committee(group_id: str, session: Session):
    config = session.exec(
        select(EventCommitteeConfig).where(EventCommitteeConfig.group_id == group_id)
    ).first()
    settings = session.exec(
        select(EventCommitteeOperationalSettings).where(EventCommitteeOperationalSettings.group_id == group_id)
    ).first()
    if not config or not settings:
        raise HTTPException(status_code=404, detail="Event Committee configuration not found for this group.")
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
        raise HTTPException(status_code=403, detail="Only the event committee admin/chairman can perform this action.")
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
        raise HTTPException(status_code=403, detail="You must be an active member of this event committee.")
    return membership


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/create", summary="Create a new Event Committee group")
def create_event_committee_group(
    request: EventCommitteeGroupCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new EVENT_COMMITTEE group (weddings, funerals, community events).
    - Creator must have KYC Tier >= 2 (National ID verified).
    - Initializes EventCommitteeConfig (budget, event date, disbursement rules).
    - Initializes EventCommitteeOperationalSettings (pledges, live collection trackers).
    - Adds creator as ADMIN and broadcasts creation to group chat.
    """
    creator = current_user
    now_ms = _now_ms()

    # 1. KYC verification
    if creator.kyc_tier < 2 or getattr(creator, "is_dependent_account", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Creating an Event Committee requires full Tier 2 National ID (NIN) verification."
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
        type="EVENT_COMMITTEE",
        payment_mode="VOLUNTARY",
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

    # 5. Create EventCommitteeConfig (Table 1)
    config = EventCommitteeConfig(
        group_id=new_group_id,
        event_target_budget=request.event_target_budget,
        event_date=request.event_date,
        collection_deadline=request.collection_deadline,
        payout_destination_type=request.payout_destination_type,
        spending_signoff_policy=request.spending_signoff_policy,
        excess_funds_action=request.excess_funds_action,
        require_invoice_upload=request.require_invoice_upload,
        created_at=now_ms
    )
    session.add(config)

    # 6. Create EventCommitteeOperationalSettings (Table 2 - defaults)
    op_settings = EventCommitteeOperationalSettings(
        group_id=new_group_id,
        allow_overfunding=False,
        track_pledges=True,
        minimum_contribution_amount=0,
        member_quota_amount=0,
        allow_guest_deposits=False,
        allow_partial_disbursements=False,
        signoff_trustee_user_ids="[]",
        current_balance=0,
        total_pledged=0,
        total_disbursed=0,
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
        logger.exception(f"Error creating event committee: {e}")
        raise HTTPException(status_code=500, detail="Database error creating event committee.")

    # 8. Broadcast greeting in chat
    broadcast_system_message_sync(
        group_id=new_group_id,
        message_text=f"{creator.full_name} established the Event Committee '{new_group.name}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(creator.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Event Committee group created successfully.",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name,
            "currency": new_group.currency,
            "event_target_budget": config.event_target_budget,
            "event_date": config.event_date,
            "collection_deadline": config.collection_deadline,
            "spending_signoff_policy": config.spending_signoff_policy,
            "excess_funds_action": config.excess_funds_action
        }
    }


@router.get("/{group_id}/dashboard", summary="View Event Committee budget progress, pledges, and countdown")
def get_event_committee_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full state of the Event Committee:
    - Creation configuration rules (Table 1)
    - Live operational settings & counters (Table 2)
    - Budget progress percentage
    - Pledge fulfillment percentage
    - Countdown to collection deadline and event date
    """
    _require_member(group_id, current_user, session)
    config, settings = _get_event_committee(group_id, session)
    now_ms = _now_ms()

    # Progress calculations
    budget_pct = None
    if config.event_target_budget > 0:
        budget_pct = round((settings.current_balance / config.event_target_budget) * 100, 2)

    pledge_fulfillment_pct = None
    if settings.total_pledged > 0:
        pledge_fulfillment_pct = round((settings.current_balance / settings.total_pledged) * 100, 2)

    days_to_deadline = max(0, int((config.collection_deadline - now_ms) / (86400 * 1000)))
    days_to_event = max(0, int((config.event_date - now_ms) / (86400 * 1000)))

    return {
        "status": "success",
        "data": {
            "event_config": config.model_dump(mode="json"),
            "operational_settings": settings.model_dump(mode="json"),
            "budget_progress_percentage": budget_pct,
            "pledge_fulfillment_percentage": pledge_fulfillment_pct,
            "days_to_deadline": days_to_deadline,
            "days_to_event": days_to_event,
            "net_available_balance": max(0, settings.current_balance)
        }
    }


@router.patch("/{group_id}/settings", summary="Admin updates mutable operational settings")
def update_event_committee_settings(
    group_id: str,
    request: UpdateEventCommitteeSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates mutable operational settings for the Event Committee:
    - allow_overfunding
    - track_pledges
    - minimum_contribution_amount
    - member_quota_amount
    - allow_guest_deposits
    - allow_partial_disbursements
    - signoff_trustee_user_ids
    """
    _require_admin(group_id, current_user, session)
    config, settings = _get_event_committee(group_id, session)

    update_dict = request.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid settings provided to update.")

    for field, val in update_dict.items():
        if field == "signoff_trustee_user_ids" and val is not None:
            settings.signoff_trustee_user_ids = json.dumps(val)
        elif hasattr(settings, field) and val is not None:
            setattr(settings, field, val)

    settings.updated_at = _now_ms()
    session.add(settings)

    try:
        session.commit()
        session.refresh(settings)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error updating event committee settings: {e}")
        raise HTTPException(status_code=500, detail="Database error updating settings.")

    return {
        "status": "success",
        "message": "Event Committee settings updated successfully.",
        "data": settings.model_dump(mode="json")
    }


@router.post("/{group_id}/submit-pledge", summary="Member submits a pledge (promise to pay)")
def submit_pledge(
    group_id: str,
    request: SubmitPledgeRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Member records a pledged amount toward the event.
    Increments total_pledged and notifies group chat.
    """
    _require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_event_committee(group_id, session)

    if not settings.track_pledges:
        raise HTTPException(status_code=400, detail="Pledge tracking is disabled for this committee.")

    if not settings.is_active:
        raise HTTPException(status_code=400, detail="This committee is closed for pledges and deposits.")

    settings.total_pledged += request.pledged_amount
    settings.updated_at = _now_ms()
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error recording pledge: {e}")
        raise HTTPException(status_code=500, detail="Database error recording pledge.")

    note_text = f" (Note: {request.note})" if request.note else ""
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"🤝 {current_user.full_name} made a pledge of {request.pledged_amount} {group.currency}{note_text}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Pledge recorded successfully.",
        "data": {
            "pledged_amount": request.pledged_amount,
            "total_pledged": settings.total_pledged
        }
    }


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
    _require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_event_committee(group_id, session)
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


@router.post("/{group_id}/close-event", summary="Admin closes committee after event completes")
def close_event(
    group_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Closes event committee collections:
    - Sets is_active = False
    - Evaluates excess funds according to excess_funds_action
      (GIFT_TO_BENEFICIARY, PROPORTIONAL_REFUND, ROLLOVER_TO_NEW_EVENT)
    - Broadcasts financial closure summary to group chat
    """
    _require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_event_committee(group_id, session)

    if not settings.is_active:
        raise HTTPException(status_code=400, detail="Event committee is already closed.")

    settings.is_active = False
    settings.updated_at = _now_ms()
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error closing event: {e}")
        raise HTTPException(status_code=500, detail="Database error closing event committee.")

    excess_balance = settings.current_balance
    action_description = {
        "GIFT_TO_BENEFICIARY": "Surplus funds will be gifted directly to the event celebrant/beneficiary.",
        "PROPORTIONAL_REFUND": "Surplus funds will be returned proportionally to contributors.",
        "ROLLOVER_TO_NEW_EVENT": "Surplus funds will rollover into a future committee fund."
    }.get(config.excess_funds_action, "Surplus funds handled per committee constitution.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=(
            f"🏁 Event Committee Closed: Collections are now finalized. "
            f"Total Disbursed: {settings.total_disbursed} {group.currency}. "
            f"Excess Balance: {excess_balance} {group.currency}. {action_description}"
        ),
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Event Committee closed successfully.",
        "data": {
            "total_disbursed": settings.total_disbursed,
            "remaining_surplus": excess_balance,
            "excess_funds_action": config.excess_funds_action,
            "action_policy": action_description
        }
    }
