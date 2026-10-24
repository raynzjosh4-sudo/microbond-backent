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
from app.models.group.welfare_event import WelfareFundConfig, WelfareFundOperationalSettings
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import WelfareFundGroupCreateRequest
from .helpers import now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

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
    current_time_ms = now_ms()

    # 1. KYC verification
    from app.services.group.group_auth_service import is_unrestricted_group_creator
    if not is_unrestricted_group_creator(creator):
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
        created_at=current_time_ms
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
