from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlmodel import Session
import uuid
import time

from app.utils.time.now_epoch_ms import now_epoch_ms
from app.core.database import get_session
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/groups/rotating", tags=["Rotating Groups"])

from app.api.routes.group.rotating.update import router as update_router
from app.api.routes.group.rotating.auction import router as auction_router
from app.api.routes.group.rotating.disburse_payout import router as disburse_router

router.include_router(update_router)
router.include_router(auction_router)
router.include_router(disburse_router)

from app.schemas.rotating_group_create_request import RotatingGroupCreateRequest
@router.post("/create")
def create_group(
    request: RotatingGroupCreateRequest, 
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Authenticate / Find creator user
    creator = current_user
        
    # --- Enforcement Checks ---
    from app.services.group.group_auth_service import is_unrestricted_group_creator
    if not is_unrestricted_group_creator(creator):
        # A. Check Full KYC Requirement (Tier 2)
        if creator.kyc_tier < 2 or getattr(creator, "is_dependent_account", False):
            raise HTTPException(
                status_code=403, 
                detail="Group creation requires full Tier 2 National ID (NIN) verification. Dependent accounts are not permitted."
            )
            
        # B. Trust Score Checks
        current_trust = creator.trust_score or 50 # Base is 50 if null
        
        # Baseline for normal groups
        if current_trust < 60:
            raise HTTPException(
                status_code=403, 
                detail="Your Trust Score is too low to create groups. Build your score by completing individual savings cycles first."
            )
            
        # Advanced groups need 80+
        ADVANCED_GROUP_TYPES = ["INVESTMENT_CLUB", "HIGH_YIELD_BIDDING", "COMMERCIAL_SYNDICATE"]
        if request.type in ADVANCED_GROUP_TYPES and current_trust < 80:
            raise HTTPException(
                status_code=403, 
                detail=f"A minimum Trust Score of 80 is required to create a {request.type}. Yours is {current_trust}."
            )
        
    # 2. Generate unique IDs and codes
    new_group_id = str(uuid.uuid4())
    invite_code = str(uuid.uuid4())[:8].upper() # 8-character invite code
    
    # 3. Create the Group (Lightweight!)
    new_group = Group(
        group_id=new_group_id,
        name=request.name,
        description=request.description,
        group_image_url=(request.group_image_url.strip() if request.group_image_url and request.group_image_url.strip() else "https://pub-2895dbbc59724eaeb22e030eb9bbdd60.r2.dev/groups/default_rotating.png"),
        type=request.type,
        payment_mode=request.payment_mode,
        visibility=request.visibility,
        currency=request.currency,
        created_by_user_id=creator.id,
        invite_code=invite_code,
        member_count=1, # Creator is the first member
        max_members=request.maximum_member_capacity
    )
    session.add(new_group)
    
    # 3b. Create Group Settings separately
    from app.models.group.settings import GroupFinancialSettings, GroupGovernanceSettings, GroupCommunicationSettings, GroupVisibilitySettings
    
    fin_settings = GroupFinancialSettings(
        group_id=new_group_id,
        enforce_payout_holds=request.enforce_payout_holds,
        enable_late_fees=request.enable_late_fees,
        late_fee_amount=request.late_fee_amount,
        late_fee_frequency=request.late_fee_frequency,
        enable_grace_period=request.enable_grace_period,
        grace_period_hours=request.grace_period_hours,
        arrears_policy=request.missed_payment_action,
        reserve_fund_percentage=request.reserve_fund_percentage,
        allow_substitute_members=request.allow_substitute_members,
        enable_escrow=request.enable_escrow,
        escrow_release_condition=request.escrow_release_condition,
        enable_timelock=request.enable_timelock,
        timelock_duration_hours=request.timelock_duration_hours
    )
    gov_settings = GroupGovernanceSettings(
        group_id=new_group_id,
        requires_admin_approval=request.requires_admin_approval,
        require_multi_signature=request.multi_sig_payout_approval
    )
    comm_settings = GroupCommunicationSettings(group_id=new_group_id)
    vis_settings = GroupVisibilitySettings(group_id=new_group_id)
    
    session.add(fin_settings)
    session.add(gov_settings)
    session.add(comm_settings)
    session.add(vis_settings)
    
    # 3c. If this is a Rotating Group, calculate cycles and save details
    if request.type == "MERRY_GO_ROUND":
        import math
        from app.models.group.rotating import RotatingGroupDetails
        
        calculated_cycles = None
        expected_pool = None  # Stays None until contribution_amount and saving_days are both set
        
        saving_days = request.saving_days_per_cycle  # e.g. 9 days
        contribution = request.contribution_amount    # e.g. 5,000 UGX per day
        
        if request.maximum_member_capacity:
            calculated_cycles = math.ceil(request.maximum_member_capacity / request.payouts_per_cycle)
        
        # Calculate total expected pool per cycle only when all values are set:
        # pool = contribution_per_interval * saving_days_per_cycle * member_count
        # e.g. 5,000 * 9 * 5 = 225,000 UGX
        if contribution is not None and saving_days is not None and request.maximum_member_capacity:
            expected_pool = contribution * saving_days * request.maximum_member_capacity
        
        # Normalize payout order strategy
        raw_strat = request.payout_order_strategy
        strat_val = raw_strat.value if hasattr(raw_strat, "value") else str(raw_strat)
        strat_upper = strat_val.upper().strip()
        if strat_upper in ["RANDOMIZED", "RANDOMIZED BY APP", "RANDOM"]:
            normalized_strategy = "Randomized by App"
        elif strat_upper in ["ADMIN ASSIGNED", "ADMIN_ASSIGNED", "ADMIN"]:
            normalized_strategy = "Admin Assigned"
        elif strat_upper in ["TRUST SCORE RANKED", "TRUST_SCORE", "TRUST"]:
            normalized_strategy = "Trust Score Ranked"
        elif strat_upper in ["FIRST COME FIRST SERVE", "FIRST_COME_FIRST_SERVE", "FCFS"]:
            normalized_strategy = "First Come First Serve"
        else:
            normalized_strategy = strat_val

        if normalized_strategy == "Admin Assigned":
            if not request.admin_assigned_order:
                raise HTTPException(
                    status_code=400, 
                    detail="Admin Assigned strategy requires a drag-and-drop order list of member IDs."
                )
            if request.maximum_member_capacity and len(request.admin_assigned_order) > request.maximum_member_capacity:
                raise HTTPException(
                    status_code=400, 
                    detail="Admin assigned list exceeds the maximum member capacity."
                )
                
        # group_start_time is Unix epoch int (ms) — default to 24h from now if missing
        start_time_val = int(request.group_start_time) if request.group_start_time else (now_epoch_ms() + 86400000)
        # collection_time string representation for VARCHAR column
        collection_time_val = str(request.collection_time) if request.collection_time is not None else None
                
        rotating_details = RotatingGroupDetails(
            group_id=new_group_id,
            contribution_amount=request.contribution_amount,
            saving_days_per_cycle=request.saving_days_per_cycle,
            payouts_per_cycle=request.payouts_per_cycle,
            number_of_cycles=calculated_cycles,
            collection_frequency_days=request.collection_frequency_days,
            collection_time=collection_time_val,
            group_start_time=start_time_val,
            payout_order_strategy=normalized_strategy,
            is_payout_order_locked=False,
            total_expected_pool_per_cycle=expected_pool,
            minimum_kyc_tier=request.minimum_kyc_tier,
            require_guarantor=request.require_guarantor,
            guarantor_default_action=request.guarantor_default_action,
            allow_partial_payments=request.allow_partial_payments,
            allow_advance_deposits=request.allow_advance_deposits,
            auto_disburse_when_full=request.auto_disburse_when_full,
            multi_sig_payout_approval=request.multi_sig_payout_approval,
            allow_turn_swaps=request.allow_turn_swaps,
            turn_swap_approval_mode=request.turn_swap_approval_mode,
            early_turn_security_hold_percentage=request.early_turn_security_hold_percentage,
            require_guarantors_for_early_turns_only=request.require_guarantors_for_early_turns_only,
            auto_renew_cycle=request.auto_renew_cycle,
            reverse_payout_order_on_renew=request.reverse_payout_order_on_renew,
            reminder_lead_time_hours=request.reminder_lead_time_hours,
            enable_auto_debit_prompt=request.enable_auto_debit_prompt
        )
        session.add(rotating_details)
    
    # 4. Create the Membership for the Creator (as ADMIN)
    new_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=new_group_id,
        user_id=creator.id,
        role="ADMIN",
        title="Creator",
        status="ACTIVE"
    )
    session.add(new_membership)

    # 5. Create the Group Wallet
    from app.models.group.wallet import GroupWallet
    new_wallet = GroupWallet(group_id=new_group_id)
    session.add(new_wallet)
    
    try:
        session.commit()
        session.refresh(new_group)
    except Exception as e:
        session.rollback()
        import traceback
        err_tb = traceback.format_exc()
        print(f"[ERROR creating rotating group]: {e}\n{err_tb}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during rotating group creation: {e}"
        )
    
    # --- NOTIFICATIONS: CHAT & CREATOR PUSH (Event 1) ---
    try:
        from app.api.routes.group.chat.messages import broadcast_system_message_sync
        from app.core.firebase_config import send_push_notification

        creator_name = creator.full_name or "Creator"
        max_cap = request.maximum_member_capacity or "?"
        
        # Handle null contribution_amount (group draft without financial terms set)
        if request.contribution_amount is not None and request.saving_days_per_cycle is not None:
            per_cycle = request.contribution_amount * request.saving_days_per_cycle
            chat_text = (
                f"{creator_name} created the group '{new_group.name}'. "
                f"Target: {request.contribution_amount:,.0f} {request.currency}/day for {request.saving_days_per_cycle} days per cycle "
                f"({per_cycle:,.0f} {request.currency} per member per cycle). "
                f"Max capacity: {max_cap} members."
            )
        elif request.contribution_amount is not None:
            chat_text = (
                f"{creator_name} created the group '{new_group.name}'. "
                f"Target: {request.contribution_amount:,.0f} {request.currency}/{request.collection_frequency_days}d. "
                f"Max capacity: {max_cap} members."
            )
        else:
            chat_text = (
                f"{creator_name} created the group '{new_group.name}'. "
                f"Financial terms (contribution amount & saving days) are not yet configured. "
                f"The admin must set them before the circle can be launched."
            )

        broadcast_system_message_sync(
            group_id=new_group_id,
            message_text=chat_text,
            message_type="SYSTEM_EVENT",
            sender_id=str(creator.id),
            session=session,
            background_tasks=background_tasks
        )

        if creator.fcm_token:
            background_tasks.add_task(
                send_push_notification,
                token=creator.fcm_token,
                title="🎉 Group Created Successfully",
                body=f"Share your 8-character invite code ({new_group.invite_code}) to recruit members. Group will launch once full.",
                data={"route": "group_invite_screen", "group_id": str(new_group_id)}
            )
    except Exception as notify_err:
        print(f"[Warning] Failed to dispatch creation notifications: {notify_err}", flush=True)
    
    return {
        "status": "success",
        "message": "Group created successfully",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name
        }
    }


@router.post("/{group_id}/launch")
def launch_rotating_group(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Manually launches a rotating group once members have joined and settings are configured.
    Enforces that contribution_amount and saving_days_per_cycle are explicitly set.
    """
    from app.models.group.rotating import RotatingGroupDetails
    from app.services.group.launcher_service import execute_group_launch

    membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == current_user.id
    ).first()

    if not membership or membership.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only group administrators can launch the circle."
        )

    group = session.query(Group).filter(Group.group_id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    details = session.query(RotatingGroupDetails).filter(RotatingGroupDetails.group_id == group_id).first()
    if not details:
        raise HTTPException(status_code=404, detail="Rotating group details not found.")

    if details.is_payout_order_locked:
        raise HTTPException(status_code=400, detail="Circle is already launched and active.")

    # Validation gates
    if details.contribution_amount is None or details.contribution_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot launch group: Contribution amount has not been configured by the admin."
        )

    if details.saving_days_per_cycle is None or details.saving_days_per_cycle < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot launch group: Saving days per cycle has not been configured by the admin."
        )

    active_members = session.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.status == "ACTIVE"
    ).all()

    if len(active_members) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot launch group: At least 2 active members are required to launch."
        )

    launched = execute_group_launch(session, group_id)
    if not launched:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to launch group. Please verify member statuses and try again."
        )

    session.commit()
    session.refresh(details)

    return {
        "status": "success",
        "message": "Rotating circle launched successfully! Cycle 1 terms are now locked.",
        "data": {
            "group_id": group_id,
            "status": group.status,
            "contribution_amount": details.contribution_amount,
            "saving_days_per_cycle": details.saving_days_per_cycle,
            "total_expected_pool_per_cycle": details.total_expected_pool_per_cycle,
            "current_cycle": details.current_cycle,
            "current_saving_day": details.current_saving_day,
            "is_payout_order_locked": details.is_payout_order_locked
        }
    }

