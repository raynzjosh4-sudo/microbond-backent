import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.models.group.settings import (
    GroupFinancialSettings,
    GroupGovernanceSettings,
    GroupCommunicationSettings,
    GroupVisibilitySettings,
)
from app.models.group.welfare_event import EventCommitteeConfig, EventCommitteeOperationalSettings
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import EventCommitteeGroupCreateRequest
from .helpers import now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

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
    current_time_ms = now_ms()

    # 1. KYC verification
    from app.services.group.group_auth_service import is_unrestricted_group_creator
    if not is_unrestricted_group_creator(creator):
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
        created_at=current_time_ms
    )
    session.add(config)

    # 6. Create EventCommitteeOperationalSettings (Table 2 - defaults)
    op_settings = EventCommitteeOperationalSettings(
        group_id=new_group_id,
        allow_overfunding=True,
        track_pledges=True,
        minimum_contribution_amount=0,
        member_quota_amount=0,
        allow_guest_deposits=True,
        allow_partial_disbursements=True,
        signoff_trustee_user_ids=None,
        total_pledged=0,
        total_disbursed=0,
        current_balance=0,
        is_active=True,
        updated_at=current_time_ms
    )
    session.add(op_settings)

    # 7. Add creator membership (ADMIN)
    session.add(GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=new_group_id,
        user_id=creator.id,
        role="ADMIN",
        status="ACTIVE",
        joined_at=current_time_ms
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
