import uuid
import time
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
from app.models.group.target_savings import TargetSavingsGroupDetails
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import TargetSavingsGroupCreateRequest
from app.services.group.authorization import grant_role

logger = logging.getLogger(__name__)

router = APIRouter()

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

    # Creator must have KYC Tier 2 (National ID verified).
    from app.services.group.group_auth_service import is_unrestricted_group_creator
    if not is_unrestricted_group_creator(creator):
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
        payment_mode=(
            "OBLIGATION" if request.allow_contribution_schedule else "VOLUNTARY"
        ),
        visibility=request.visibility,
        currency=request.currency,
        start_date=request.start_date,
        max_members=request.max_members if request.allow_max_members else None,
        created_by_user_id=creator.id,
        invite_code=invite_code,
        member_count=1
    )
    session.add(new_group)

    # 6. Create Base Settings
    session.add(
        GroupFinancialSettings(
            group_id=new_group_id,
            enable_late_fees=request.enable_late_fees,
            late_fee_amount=float(request.late_fee_amount),
            grace_period_hours=request.grace_period_hours,
        )
    )
    session.add(
        GroupGovernanceSettings(
            group_id=new_group_id,
            minimum_kyc_tier=request.minimum_kyc_tier,
        )
    )
    session.add(GroupCommunicationSettings(group_id=new_group_id))
    session.add(GroupVisibilitySettings(group_id=new_group_id))

    # 7. Create Target Savings Details
    target_details = TargetSavingsGroupDetails(
        group_id=new_group_id,
        allow_target_amount=request.allow_target_amount,
        allow_target_date=request.allow_target_date,
        allow_contribution_schedule=request.allow_contribution_schedule,
        allow_collection_frequency=request.allow_collection_frequency,
        target_amount=request.target_amount if request.allow_target_amount else None,
        target_date=request.target_date if request.allow_target_date else None,
        contribution_amount=request.contribution_amount,
        collection_frequency_days=request.collection_frequency_days,
        collection_time=request.collection_time,
        allow_multi_payout=request.allow_multi_payout,
        payout_destination_type=(
            "PROPORTIONAL_RETURN" if request.allow_multi_payout else "SINGLE_NOMINATED_ACCOUNT"
        ),
        require_consensus_at_end=request.require_consensus_at_end,
        allow_early_payout_by_vote=request.allow_early_payout_by_vote,
        vote_approval_percentage=request.vote_approval_percentage,
        enable_late_fees=request.enable_late_fees,
        late_fee_amount=request.late_fee_amount,
        grace_period_hours=request.grace_period_hours,
        missed_payment_action=request.missed_payment_action,
        minimum_kyc_tier=request.minimum_kyc_tier,
        hide_leaderboard=request.hide_leaderboard,
        is_locked=False,
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
    grant_role(session, new_group_id, creator.id, "ADMIN", creator.id)

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
            "start_date": new_group.start_date,
            "max_members": new_group.max_members,
            "target_amount": target_details.target_amount,
            "target_date": target_details.target_date,
            "contribution_amount": target_details.contribution_amount,
            "allow_collection_frequency": target_details.allow_collection_frequency,
            "payout_destination_type": target_details.payout_destination_type
        }
    }
