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
from app.models.group.long_term import FundraiserCampaignConfig, FundraiserLiveStats
from app.models.group.chat import GroupPoll
from app.schemas.fundraiser_group_create_request import FundraiserGroupCreateRequest
from app.api.routes.group.chat.messages import broadcast_system_message_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups/fundraiser", tags=["Fundraiser Groups"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class UpdateFundraiserSettingsRequest(BaseModel):
    allow_overfunding: Optional[bool] = Field(
        default=None,
        description="Allow donations even after the target amount is reached."
    )
    stop_on_target_reached: Optional[bool] = Field(
        default=None,
        description="Auto-close the campaign the moment the target is reached."
    )
    minimum_donation_amount: Optional[int] = Field(
        default=None, ge=0,
        description="Smallest donation accepted (whole currency units, e.g. 500 UGX)."
    )


class RequestSignoffBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500,
                        description="Why you want to release the funds now.")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_campaign(group_id: str, session: Session):
    config = session.exec(
        select(FundraiserCampaignConfig).where(FundraiserCampaignConfig.group_id == group_id)
    ).first()
    stats = session.exec(
        select(FundraiserLiveStats).where(FundraiserLiveStats.group_id == group_id)
    ).first()
    if not config or not stats:
        raise HTTPException(status_code=404, detail="Fundraiser details not found for this group.")
    return config, stats


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
        raise HTTPException(status_code=403, detail="Only the group admin can do this.")
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
    now_ms = _now_ms()

    # 1. KYC guard
    if creator.kyc_tier < 2 or getattr(creator, "is_dependent_account", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Starting a fundraiser requires full Tier 2 National ID (NIN) verification."
        )

    # 2. Validation: campaign_deadline must be in the future if provided
    if request.campaign_deadline is not None and request.campaign_deadline <= now_ms:
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
        created_at=now_ms
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
        updated_at=now_ms
    )
    session.add(live_stats)

    # 8. Creator membership (ADMIN)
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


@router.get("/{group_id}/dashboard", summary="View campaign status and stats")
def get_fundraiser_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the full campaign picture: locked config + live stats + calculated progress.
    Any active member of the group can view this.
    """
    _require_member(group_id, current_user, session)
    config, stats = _get_campaign(group_id, session)

    # Calculate progress percentage
    if config.target_amount > 0:
        progress_pct = round((stats.total_raised / config.target_amount) * 100, 2)
    else:
        progress_pct = None  # open-ended, no target to measure against

    # Calculate days remaining
    if config.campaign_deadline:
        ms_remaining = config.campaign_deadline - _now_ms()
        days_remaining = max(0, ms_remaining // (1000 * 60 * 60 * 24))
    else:
        days_remaining = None

    return {
        "status": "success",
        "data": {
            "campaign_config": config.model_dump(mode="json"),
            "live_stats": stats.model_dump(mode="json"),
            "progress_percentage": progress_pct,
            "days_remaining": days_remaining
        }
    }


@router.patch("/{group_id}/settings", summary="Update campaign settings")
def update_fundraiser_settings(
    group_id: str,
    request: UpdateFundraiserSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin updates the mutable campaign settings (FundraiserLiveStats fields only).
    Locked config fields (target, deadline, payout destination) cannot be changed.
    """
    _require_admin(group_id, current_user, session)
    _, stats = _get_campaign(group_id, session)

    if stats.is_paid_out:
        raise HTTPException(status_code=400, detail="Cannot update settings for a fundraiser that has already paid out.")

    if request.allow_overfunding is not None:
        stats.allow_overfunding = request.allow_overfunding
    if request.stop_on_target_reached is not None:
        stats.stop_on_target_reached = request.stop_on_target_reached
    if request.minimum_donation_amount is not None:
        stats.minimum_donation_amount = request.minimum_donation_amount

    stats.updated_at = _now_ms()
    session.add(stats)
    session.commit()
    session.refresh(stats)

    return {
        "status": "success",
        "message": "Fundraiser settings updated.",
        "data": stats.model_dump(mode="json")
    }


@router.post("/{group_id}/close-campaign", summary="Stop accepting donations")
def close_campaign(
    group_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin closes the campaign — no new donations will be accepted.
    The money is NOT released here. Use release-funds or request-signoff for that.
    """
    _require_admin(group_id, current_user, session)
    _, stats = _get_campaign(group_id, session)

    if not stats.is_active:
        raise HTTPException(status_code=400, detail="This campaign is already closed.")
    if stats.is_paid_out:
        raise HTTPException(status_code=400, detail="This fundraiser has already paid out.")

    stats.is_active = False
    stats.updated_at = _now_ms()
    session.add(stats)
    session.commit()

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"{current_user.full_name} has closed this fundraiser. No new donations are being accepted.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Campaign closed. No more donations will be accepted."
    }


@router.post("/{group_id}/request-signoff", summary="Ask signers to approve the money release")
def request_signoff(
    group_id: str,
    request: RequestSignoffBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Only used when require_multi_signoff is True.
    Creates a group vote (poll) so the required signers can approve releasing the money.
    """
    _require_admin(group_id, current_user, session)
    config, stats = _get_campaign(group_id, session)

    if not config.require_multi_signoff:
        raise HTTPException(
            status_code=400,
            detail="This fundraiser does not require multi-signoff. Use release-funds directly."
        )
    if stats.is_paid_out:
        raise HTTPException(status_code=400, detail="This fundraiser has already paid out.")

    now_ms = _now_ms()
    expires_at = now_ms + (48 * 3600 * 1000)  # 48-hour voting window

    poll = GroupPoll(
        group_id=group_id,
        creator_id=current_user.id,
        question=f"Approve releasing all collected funds? Reason: {request.reason}",
        options=json.dumps(["Approve Release", "Do Not Release Yet"]),
        poll_type="FUND_RELEASE",
        status="OPEN",
        expires_at=expires_at,
        created_at=now_ms
    )
    session.add(poll)
    session.commit()
    session.refresh(poll)

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=json.dumps({
            "poll_id": str(poll.id),
            "question": poll.question,
            "options": ["Approve Release", "Do Not Release Yet"],
            "signoff_count_required": config.signoff_count_required
        }),
        message_type="VOTE",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Signoff request sent to the group chat.",
        "data": {
            "poll_id": str(poll.id),
            "signoff_count_required": config.signoff_count_required,
            "expires_at": poll.expires_at
        }
    }


@router.post("/{group_id}/release-funds", summary="Send the collected money to the destination")
def release_funds(
    group_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Releases the collected funds.
    - If require_multi_signoff is False: admin calls this directly.
    - If require_multi_signoff is True: checks that an approved FUND_RELEASE poll exists.
    """
    _require_admin(group_id, current_user, session)
    config, stats = _get_campaign(group_id, session)

    if stats.is_paid_out:
        raise HTTPException(status_code=400, detail="Funds have already been released for this fundraiser.")
    if stats.total_raised <= 0:
        raise HTTPException(status_code=400, detail="No funds have been collected yet.")

    # If multi-signoff required, verify an approved FUND_RELEASE poll exists
    if config.require_multi_signoff:
        approved_poll = session.exec(
            select(GroupPoll).where(
                GroupPoll.group_id == group_id,
                GroupPoll.poll_type == "FUND_RELEASE",
                GroupPoll.status == "CLOSED"
            )
        ).first()
        if not approved_poll:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"This fundraiser requires {config.signoff_count_required} signers to approve "
                    "before funds can be released. Please use request-signoff first."
                )
            )

    # Mark as paid out
    stats.is_paid_out = True
    stats.is_active = False
    stats.updated_at = _now_ms()
    session.add(stats)
    session.commit()

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=(
            f"{current_user.full_name} has released the collected funds "
            f"({stats.total_raised:,} {config.payout_destination_type}) to the designated account."
        ),
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Funds released successfully.",
        "data": {
            "total_released": stats.total_raised,
            "payout_destination_type": config.payout_destination_type,
            "nominated_account_id": config.nominated_account_id
        }
    }
