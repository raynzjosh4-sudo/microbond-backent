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
from app.models.group.long_term import FundraiserCampaignConfig, FundraiserLiveStats
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import FundraiserGroupCreateRequest
from .helpers import now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/create", summary="Start a new fundraiser campaign")
def create_fundraiser(
    request: FundraiserGroupCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new FUNDRAISER group.
    The creator must have KYC Tier 2 (National ID verified).
    Locked config fields are set here. Live settings are auto-created with safe defaults.
    """
    creator = current_user
    current_time_ms = now_ms()

    # 1. KYC guard
    if creator.kyc_tier < 2 or getattr(creator, "is_dependent_account", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Starting a fundraiser requires full Tier 2 National ID (NIN) verification."
        )

    # 2. Validation: campaign_deadline must be in the future if provided
    if request.campaign_deadline is not None and request.campaign_deadline <= current_time_ms:
        raise HTTPException(status_code=400, detail="Campaign deadline must be in the future.")

    # 3. Build IDs
    new_group_id = str(uuid.uuid4())
    invite_code = str(uuid.uuid4())[:8].upper()

    # 4. Create Group
    new_group = Group(
        group_id=new_group_id,
        name=request.name,
        description=request.description,
        group_image_url=request.group_image_url,
        type="FUNDRAISER",
        payment_mode="VOLUNTARY",
        visibility=request.visibility,
        currency=request.currency,
        created_by_user_id=creator.id,
        invite_code=invite_code,
        member_count=1
    )
    session.add(new_group)

    # 5. Create base settings (reuse shared tables)
    session.add(GroupFinancialSettings(group_id=new_group_id))
    session.add(GroupGovernanceSettings(group_id=new_group_id))
    session.add(GroupCommunicationSettings(group_id=new_group_id))
    session.add(GroupVisibilitySettings(group_id=new_group_id))

    # 6. Create locked campaign config
    campaign_config = FundraiserCampaignConfig(
        group_id=new_group_id,
        target_amount=request.target_amount,
        campaign_deadline=request.campaign_deadline,
        payout_destination_type=request.payout_destination_type,
        nominated_account_id=request.nominated_account_id,
        payout_trigger_mode=request.payout_trigger_mode,
        require_multi_signoff=request.require_multi_signoff,
        signoff_count_required=request.signoff_count_required,
        created_at=current_time_ms
    )
    session.add(campaign_config)

    # 7. Auto-create live stats with defaults
    live_stats = FundraiserLiveStats(
        group_id=new_group_id,
        allow_overfunding=True,
        stop_on_target_reached=False,
        minimum_donation_amount=500,
        is_active=True,
        is_paid_out=False,
        total_raised=0,
        donor_count=0,
        updated_at=current_time_ms
    )
    session.add(live_stats)

    # 8. Creator membership (ADMIN)
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
        session.refresh(campaign_config)
    except Exception as e:
        session.rollback()
        logger.exception(f"Failed to create fundraiser group: {e}")
        raise HTTPException(status_code=500, detail="Database error while creating the fundraiser.")

    # 9. Broadcast system message
    broadcast_system_message_sync(
        group_id=new_group_id,
        message_text=f"{creator.full_name} started a fundraiser: '{new_group.name}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(creator.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Fundraiser created successfully.",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name,
            "target_amount": campaign_config.target_amount,
            "campaign_deadline": campaign_config.campaign_deadline,
            "payout_destination_type": campaign_config.payout_destination_type,
            "payout_trigger_mode": campaign_config.payout_trigger_mode,
            "require_multi_signoff": campaign_config.require_multi_signoff,
        }
    }
