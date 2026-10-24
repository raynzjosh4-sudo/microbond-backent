import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.models.group.settings import GroupFinancialSettings, GroupGovernanceSettings, GroupCommunicationSettings, GroupVisibilitySettings
from app.models.group.investment_association import AssociationDuesConfig, AssociationDuesOperationalSettings, AssociationMemberDuesStanding
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import AssociationDuesGroupCreateRequest
from .helpers import now_ms as _now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/create", summary="Create a new Association Dues group")
def create_association_dues_group(
    request: AssociationDuesGroupCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new ASSOCIATION_DUES group (Alumni networks, HOAs, unions, professional bodies).
    - Creator must have KYC Tier >= 2 (National ID verified).
    - Initializes AssociationDuesConfig (locked dues and billing schedule).
    - Initializes AssociationDuesOperationalSettings (sweep triggers, late fees, defaulter rules).
    - Adds creator as ADMIN and initializes member dues standing.
    """
    creator = current_user
    now_ms = _now_ms()

    # 1. KYC verification
    from app.services.group.group_auth_service import is_unrestricted_group_creator
    if not is_unrestricted_group_creator(creator):
        if creator.kyc_tier < 2 or getattr(creator, "is_dependent_account", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Creating an Association group requires full Tier 2 National ID (NIN) verification."
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
        type="ASSOCIATION_DUES",
        payment_mode="OBLIGATION",
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

    # 5. AssociationDuesConfig (Table 1)
    config = AssociationDuesConfig(
        group_id=new_group_id,
        dues_amount=request.dues_amount,
        billing_cycle_days=request.billing_cycle_days,
        billing_start_date=request.billing_start_date,
        treasury_account_id=request.treasury_account_id,
        enable_prorated_dues=request.enable_prorated_dues,
        created_at=now_ms
    )
    session.add(config)

    # 6. AssociationDuesOperationalSettings (Table 2 - defaults)
    op_settings = AssociationDuesOperationalSettings(
        group_id=new_group_id,
        auto_sweep_trigger="END_OF_CYCLE",
        allow_advance_payments=True,
        grace_period_days=7,
        late_fee_amount=0,
        arrears_action="SUSPEND_MEMBERSHIP",
        max_missed_cycles_allowed=3,
        show_defaulters_publicly=False,
        treasury_ledger_visibility="TRANSPARENT",
        allow_installments=True,
        send_arrears_reminders=True,
        arrears_reminder_days_before=3,
        restrict_voting_on_arrears=True,
        restrict_welfare_claims_on_arrears=True,
        current_balance=0,
        total_collected=0,
        total_swept_to_treasury=0,
        active_defaulters_count=0,
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

    # 8. Creator dues standing
    session.add(AssociationMemberDuesStanding(
        group_id=new_group_id,
        user_id=creator.id,
        cycles_paid_ahead=0,
        consecutive_missed_cycles=0,
        outstanding_arrears_balance=0,
        is_in_arrears=False,
        is_suspended=False,
        last_payment_date=None,
        next_due_date=request.billing_start_date,
        updated_at=now_ms
    ))

    try:
        session.commit()
        session.refresh(new_group)
        session.refresh(config)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error creating association dues group: {e}")
        raise HTTPException(status_code=500, detail="Database error creating association dues group.")

    broadcast_system_message_sync(
        group_id=new_group_id,
        message_text=f"{creator.full_name} established the Association '{new_group.name}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(creator.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Association Dues group created successfully.",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name,
            "currency": new_group.currency,
            "dues_amount": config.dues_amount,
            "billing_cycle_days": config.billing_cycle_days,
            "billing_start_date": config.billing_start_date,
            "treasury_account_id": config.treasury_account_id
        }
    }
