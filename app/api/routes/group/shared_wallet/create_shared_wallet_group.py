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
from app.models.group.long_term import SharedWalletConfig, SharedWalletOperationalSettings
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import SharedWalletGroupCreateRequest
from .helpers import now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/create", summary="Create a new Shared Wallet group")
def create_shared_wallet_group(
    request: SharedWalletGroupCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new SHARED_WALLET group.
    - Creator must have KYC Tier >= 2 (National ID verified).
    - Initializes SharedWalletConfig (locked creation parameters).
    - Initializes SharedWalletOperationalSettings (default operational limits).
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
                detail="Creating a Shared Wallet requires full Tier 2 National ID (NIN) verification."
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
        type="SHARED_WALLET",
        payment_mode="MIXED",
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

    # 5. Create SharedWalletConfig (Table 1)
    config = SharedWalletConfig(
        group_id=new_group_id,
        replenishment_mode=request.replenishment_mode,
        member_quota_amount=request.member_quota_amount,
        collection_frequency_days=request.collection_frequency_days,
        spending_signoff_policy=request.spending_signoff_policy,
        exit_payout_rule=request.exit_payout_rule,
        track_individual_contributions=request.track_individual_contributions,
        minimum_kyc_tier=request.minimum_kyc_tier,
        created_at=current_time_ms
    )
    session.add(config)

    # 6. Create SharedWalletOperationalSettings (Table 2 - defaults)
    op_settings = SharedWalletOperationalSettings(
        group_id=new_group_id,
        minimum_balance_floor=0,
        target_budget_limit=None,
        auto_approve_threshold=0,
        approval_timeout_hours=48,
        timelock_duration_hours=0,
        daily_spending_cap=None,
        per_transaction_cap=None,
        allowed_disbursement_types='["MEMBER_ACCOUNTS", "EXTERNAL_PAYEES"]',
        current_balance=0,
        total_deposited=0,
        total_spent=0,
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
        logger.exception(f"Error creating shared wallet: {e}")
        raise HTTPException(status_code=500, detail="Database error creating shared wallet.")

    # 8. Broadcast greeting in chat
    broadcast_system_message_sync(
        group_id=new_group_id,
        message_text=f"{creator.full_name} created the Shared Wallet '{new_group.name}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(creator.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Shared Wallet group created successfully.",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name,
            "currency": new_group.currency,
            "replenishment_mode": config.replenishment_mode,
            "spending_signoff_policy": config.spending_signoff_policy,
            "exit_payout_rule": config.exit_payout_rule
        }
    }
