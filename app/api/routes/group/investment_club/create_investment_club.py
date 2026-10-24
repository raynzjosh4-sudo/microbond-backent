import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.models.group.settings import GroupFinancialSettings, GroupGovernanceSettings, GroupCommunicationSettings, GroupVisibilitySettings
from app.models.group.investment_association import InvestmentClubConfig, InvestmentClubOperationalSettings, InvestmentClubMemberShare
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import InvestmentClubGroupCreateRequest
from .helpers import now_ms as _now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/create", summary="Create a new Investment Club group")
def create_investment_club(
    request: InvestmentClubGroupCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new INVESTMENT_CLUB group.
    - Creator must have KYC Tier >= 2 (National ID verified).
    - Initializes InvestmentClubConfig (locked equity and voting model).
    - Initializes InvestmentClubOperationalSettings (quotas, fees, live counters).
    - Adds creator as ADMIN and initializes member share ledger.
    """
    creator = current_user
    now_ms = _now_ms()

    # 1. KYC verification
    from app.services.group.group_auth_service import is_unrestricted_group_creator
    if not is_unrestricted_group_creator(creator):
        if creator.kyc_tier < 2 or getattr(creator, "is_dependent_account", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Creating an Investment Club requires full Tier 2 National ID (NIN) verification."
            )

    # 2. Identifiers
    new_group_id = str(uuid.uuid4())
    invite_code = str(uuid.uuid4())[:8].upper()

    # 3. Create Group
    new_group = Group(
        group_id=new_group_id,
        name=request.name,
        description=request.description,
        group_image_url=request.group_image_url,
        type="INVESTMENT_CLUB",
        payment_mode="VOLUNTARY",
        visibility=request.visibility,
        currency=request.currency,
        created_by_user_id=creator.id,
        invite_code=invite_code,
        member_count=1
    )
    session.add(new_group)

    # 4. Base settings
    session.add(GroupFinancialSettings(group_id=new_group_id))
    session.add(GroupGovernanceSettings(group_id=new_group_id))
    session.add(GroupCommunicationSettings(group_id=new_group_id))
    session.add(GroupVisibilitySettings(group_id=new_group_id))

    # 5. InvestmentClubConfig (Table 1)
    config = InvestmentClubConfig(
        group_id=new_group_id,
        share_unit_price=request.share_unit_price,
        equity_calculation_mode=request.equity_calculation_mode,
        voting_power_logic=request.voting_power_logic,
        payout_destination_type=request.payout_destination_type,
        dividend_distribution_rule=request.dividend_distribution_rule,
        lock_in_period_days=request.lock_in_period_days,
        liquidation_action=request.liquidation_action,
        created_at=now_ms
    )
    session.add(config)

    # 6. InvestmentClubOperationalSettings (Table 2 - defaults)
    op_settings = InvestmentClubOperationalSettings(
        group_id=new_group_id,
        minimum_purchase_quota=0,
        proposal_approval_threshold_pct=66,
        admin_management_fee_pct=0,
        allow_internal_share_transfers=True,
        enable_late_fees=False,
        current_balance=0,
        total_invested_capital=0,
        total_shares_issued=0,
        total_dividends_distributed=0,
        is_active=True,
        updated_at=now_ms
    )
    session.add(op_settings)

    # 7. Creator membership (ADMIN)
    session.add(GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=new_group_id,
        user_id=creator.id,
        role="ADMIN",
        status="ACTIVE",
        joined_at=now_ms
    ))

    # 8. Creator share ledger
    session.add(InvestmentClubMemberShare(
        group_id=new_group_id,
        user_id=creator.id,
        shares_owned=0,
        total_invested=0,
        last_dividend_received=0,
        created_at=now_ms,
        updated_at=now_ms
    ))

    try:
        session.commit()
        session.refresh(new_group)
        session.refresh(config)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error creating investment club: {e}")
        raise HTTPException(status_code=500, detail="Database error creating investment club.")

    broadcast_system_message_sync(
        group_id=new_group_id,
        message_text=f"{creator.full_name} established the Investment Club '{new_group.name}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(creator.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Investment Club created successfully.",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name,
            "currency": new_group.currency,
            "share_unit_price": config.share_unit_price,
            "equity_calculation_mode": config.equity_calculation_mode,
            "voting_power_logic": config.voting_power_logic,
            "dividend_distribution_rule": config.dividend_distribution_rule,
            "lock_in_period_days": config.lock_in_period_days
        }
    }

