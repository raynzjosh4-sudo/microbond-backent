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
from app.models.group.settings import GroupFinancialSettings, GroupGovernanceSettings, GroupCommunicationSettings, GroupVisibilitySettings
from app.models.group.long_term import TargetSavingsGroupDetails
from app.models.group.chat import GroupPoll
from app.schemas.target_savings_group_create_request import TargetSavingsGroupCreateRequest
from app.api.routes.group.chat.messages import broadcast_system_message_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups/target-savings", tags=["Target Savings Groups"])

class UpdateTargetSavingsSettingsRequest(BaseModel):
    contribution_amount: Optional[int] = Field(default=None, ge=0, description="Amount each member must save per cycle")
    collection_frequency_days: Optional[int] = Field(default=None, ge=0, description="0=Flexible/Daily, 7=Weekly, 14=Bi-weekly, 30=Monthly")
    collection_time: Optional[int] = Field(default=None, description="Cutoff time of day in milliseconds")
    
    # Consensus & Voting Rules
    require_consensus_at_end: Optional[bool] = Field(default=None, description="Require members to vote to release money at the target date")
    allow_early_payout_by_vote: Optional[bool] = Field(default=None, description="Allow members to vote to end savings early")
    vote_approval_percentage: Optional[int] = Field(default=None, ge=51, le=100, description="Percentage of members who must agree (51-100%)")
    
    # Late Fees & Rules
    enable_late_fees: Optional[bool] = Field(default=None, description="Charge a small fee if a member pays late")
    late_fee_amount: Optional[int] = Field(default=None, ge=0, description="Flat late fee in whole currency units")
    grace_period_hours: Optional[int] = Field(default=None, ge=0, description="Hours of grace before late fee applies")
    missed_payment_action: Optional[str] = Field(default=None, description="RECORD_STRIKE or REMOVE_AND_REFUND")
    minimum_kyc_tier: Optional[int] = Field(default=None, ge=0, le=3, description="Minimum verification tier required to join (0-3)")
    hide_leaderboard: Optional[bool] = Field(default=None, description="Hide member contribution rankings")

class EarlyPayoutProposalRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500, description="Reason for requesting to end savings early")

@router.post("/create", summary="Create a new Target Savings Group")
def create_target_savings_group(
    request: TargetSavingsGroupCreateRequest, 
    background_tasks: BackgroundTasks, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new target savings group with locked maturity date, strict integer money values,
    and configured consensus voting rules.
    """
    creator = current_user
    now_ms = int(time.time() * 1000)

    # 1. Validation: target_date must be in the future
    if request.target_date <= now_ms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target date must be in the future."
        )

    # 2. Validation: SINGLE_NOMINATED_ACCOUNT requires nominated_account_id
    if request.payout_destination_type == "SINGLE_NOMINATED_ACCOUNT" and not request.nominated_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nominated account ID is required when payout destination is set to SINGLE_NOMINATED_ACCOUNT."
        )

    # 3. Validation: Creator must have KYC Tier 2 (National ID verified)
    if creator.kyc_tier < 2 or getattr(creator, "is_dependent_account", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Group creation requires full Tier 2 National ID (NIN) verification. Dependent accounts are not permitted."
        )

    # 4. Generate unique IDs
    new_group_id = str(uuid.uuid4())
    invite_code = str(uuid.uuid4())[:8].upper()

    # 5. Create Group
    new_group = Group(
        group_id=new_group_id,
        name=request.name,
        description=request.description,
        group_image_url=request.group_image_url,
        type="GOAL_SAVINGS",
        payment_mode=request.payment_mode,
        visibility=request.visibility,
        currency=request.currency,
        created_by_user_id=creator.id,
        invite_code=invite_code,
        member_count=1
    )
    session.add(new_group)

    # 6. Create Base Settings
    session.add(GroupFinancialSettings(group_id=new_group_id))
    session.add(GroupGovernanceSettings(group_id=new_group_id))
    session.add(GroupCommunicationSettings(group_id=new_group_id))
    session.add(GroupVisibilitySettings(group_id=new_group_id))

    # 7. Create Target Savings Details
    target_details = TargetSavingsGroupDetails(
        group_id=new_group_id,
        target_amount=request.target_amount,
        target_date=request.target_date,
        contribution_amount=request.contribution_amount,
        collection_frequency_days=request.collection_frequency_days,
        collection_time=request.collection_time,
        payout_destination_type=request.payout_destination_type,
        nominated_account_id=request.nominated_account_id,
        require_consensus_at_end=request.require_consensus_at_end,
        allow_early_payout_by_vote=request.allow_early_payout_by_vote,
        vote_approval_percentage=request.vote_approval_percentage,
        enable_late_fees=request.enable_late_fees,
        late_fee_amount=request.late_fee_amount,
        grace_period_hours=request.grace_period_hours,
        missed_payment_action=request.missed_payment_action,
        minimum_kyc_tier=request.minimum_kyc_tier,
        hide_leaderboard=request.hide_leaderboard,
        is_locked=True,
        is_ended=False,
        is_paid_out=False,
        total_saved_amount=0,
        created_at=now_ms
    )
    session.add(target_details)

    # 8. Create Creator Membership (ADMIN)
    new_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=new_group_id,
        user_id=creator.id,
        role="ADMIN",
        status="ACTIVE",
        joined_at=now_ms
    )
    session.add(new_membership)

    try:
        session.commit()
        session.refresh(new_group)
        session.refresh(target_details)
    except Exception as e:
        session.rollback()
        logger.exception(f"Failed to create target savings group: {e}")
        raise HTTPException(status_code=500, detail="Database error creating savings group.")

    # 9. Broadcast system greeting to group chat
    broadcast_system_message_sync(
        group_id=new_group_id,
        message_text=f"{creator.full_name} created the Target Savings group '{new_group.name}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(creator.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Target Savings Group created successfully",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name,
            "target_amount": target_details.target_amount,
            "target_date": target_details.target_date,
            "contribution_amount": target_details.contribution_amount,
            "payout_destination_type": target_details.payout_destination_type
        }
    }

@router.get("/{group_id}/settings", summary="Get Target Savings Group Settings")
def get_target_savings_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the target savings rules, current saved totals, and consensus settings for active members.
    """
    # Verify membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")

    details = session.exec(
        select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
    ).first()
    if not details:
        raise HTTPException(status_code=404, detail="Target savings details not found for this group.")

    return {
        "status": "success",
        "data": details.model_dump(mode="json")
    }

@router.patch("/{group_id}/settings", summary="Update Target Savings Group Settings")
def update_target_savings_settings(
    group_id: str,
    request: UpdateTargetSavingsSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Allows the group Admin to update non-locked settings.
    Settings like target_date and payout_destination_type are locked to protect member funds.
    """
    # 1. Verify Admin
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update group settings.")

    details = session.exec(
        select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id).with_for_update()
    ).first()
    if not details:
        raise HTTPException(status_code=404, detail="Target savings details not found.")

    if details.is_ended or details.is_paid_out:
        raise HTTPException(status_code=400, detail="Cannot modify settings for an ended savings group.")

    # 2. Apply updates
    if request.contribution_amount is not None:
        details.contribution_amount = request.contribution_amount
    if request.collection_frequency_days is not None:
        details.collection_frequency_days = request.collection_frequency_days
    if request.collection_time is not None:
        details.collection_time = request.collection_time
    if request.require_consensus_at_end is not None:
        details.require_consensus_at_end = request.require_consensus_at_end
    if request.allow_early_payout_by_vote is not None:
        details.allow_early_payout_by_vote = request.allow_early_payout_by_vote
    if request.vote_approval_percentage is not None:
        details.vote_approval_percentage = request.vote_approval_percentage
    if request.enable_late_fees is not None:
        details.enable_late_fees = request.enable_late_fees
    if request.late_fee_amount is not None:
        details.late_fee_amount = request.late_fee_amount
    if request.grace_period_hours is not None:
        details.grace_period_hours = request.grace_period_hours
    if request.missed_payment_action is not None:
        details.missed_payment_action = request.missed_payment_action
    if request.minimum_kyc_tier is not None:
        details.minimum_kyc_tier = request.minimum_kyc_tier
    if request.hide_leaderboard is not None:
        details.hide_leaderboard = request.hide_leaderboard

    session.add(details)
    session.commit()
    session.refresh(details)

    return {
        "status": "success",
        "message": "Target savings settings updated successfully",
        "data": details.model_dump(mode="json")
    }

@router.post("/{group_id}/request-early-payout", summary="Request Group Vote to End Savings Early")
def request_early_payout(
    group_id: str,
    request: EarlyPayoutProposalRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Launches a group vote in the chat so members can decide whether to end savings early
    and receive their money back.
    """
    # 1. Verify Active Membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member to request early payout.")

    details = session.exec(
        select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
    ).first()
    if not details:
        raise HTTPException(status_code=404, detail="Target savings details not found.")

    if not details.allow_early_payout_by_vote:
        raise HTTPException(status_code=400, detail="This group does not allow early payout votes.")

    if details.is_ended or details.is_paid_out:
        raise HTTPException(status_code=400, detail="This savings group has already ended.")

    # 2. Create a GroupPoll for consensus voting
    now_ms = int(time.time() * 1000)
    expires_at = now_ms + (24 * 3600 * 1000) # 24 hours voting window
    poll = GroupPoll(
        group_id=group_id,
        creator_id=current_user.id,
        question=f"End savings early and receive payouts? Reason: {request.reason}",
        options=json.dumps(["Approve Early Payout", "Keep Saving Until Target Date"]),
        poll_type="EARLY_PAYOUT",
        status="OPEN",
        expires_at=expires_at,
        created_at=now_ms
    )
    session.add(poll)
    session.commit()
    session.refresh(poll)

    # 3. Broadcast Poll to Group Chat
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=json.dumps({
            "poll_id": str(poll.id),
            "question": poll.question,
            "options": ["Approve Early Payout", "Keep Saving Until Target Date"],
            "vote_approval_percentage": details.vote_approval_percentage
        }),
        message_type="VOTE",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Early payout vote proposed and broadcast to chat.",
        "data": {
            "poll_id": str(poll.id),
            "expires_at": poll.expires_at,
            "vote_approval_percentage": details.vote_approval_percentage
        }
    }
