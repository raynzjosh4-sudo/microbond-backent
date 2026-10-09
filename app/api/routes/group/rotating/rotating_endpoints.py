from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlmodel import Session
import uuid
import time

from app.core.database import get_session
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/groups/rotating", tags=["Rotating Groups"])

from app.api.routes.group.rotating.update import router as update_router
router.include_router(update_router)

from app.schemas.rotating_group_create_request import RotatingGroupCreateRequest
@router.post("/create")
def create_group(
    request: RotatingGroupCreateRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Authenticate / Find creator user
    creator = current_user
        
    # --- Enforcement Checks ---
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
        group_image_url=request.group_image_url,
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
        requires_admin_approval=request.requires_admin_approval
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
        expected_pool = request.contribution_amount
        if request.maximum_member_capacity:
            calculated_cycles = math.ceil(request.maximum_member_capacity / request.payouts_per_cycle)
            expected_pool = request.contribution_amount * request.maximum_member_capacity
        
        if request.payout_order_strategy == "Admin Assigned":
            if not request.admin_assigned_order:
                raise HTTPException(
                    status_code=400, 
                    detail="Admin Assigned strategy requires a drag-and-drop order list of member IDs."
                )
            if len(request.admin_assigned_order) > request.maximum_member_capacity:
                raise HTTPException(
                    status_code=400, 
                    detail="Admin assigned list exceeds the maximum member capacity."
                )
                
        # Handle IMMEDIATE start time
        start_time_val = request.group_start_time
        if isinstance(start_time_val, str) and start_time_val.upper() == "IMMEDIATE":
            start_time_val = int(time.time())
        else:
            try:
                start_time_val = int(start_time_val)
            except ValueError:
                start_time_val = int(time.time())
                
        rotating_details = RotatingGroupDetails(
            group_id=new_group_id,
            contribution_amount=request.contribution_amount,
            payouts_per_cycle=request.payouts_per_cycle,
            number_of_cycles=calculated_cycles,
            collection_frequency_days=request.collection_frequency_days,
            collection_time=request.collection_time,
            group_start_time=start_time_val,
            payout_order_strategy=request.payout_order_strategy.value,
            is_payout_order_locked=False,
            total_expected_pool_per_cycle=expected_pool,
            minimum_kyc_tier=request.minimum_kyc_tier,
            require_guarantor=request.require_guarantor,
            guarantor_default_action=request.guarantor_default_action,
            allow_partial_payments=request.allow_partial_payments,
            allow_advance_deposits=request.allow_advance_deposits,
            enforce_payout_holds=request.enforce_payout_holds
        )
        session.add(rotating_details)
    
    # 4. Create the Membership for the Creator (as ADMIN)
    new_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=new_group_id,
        user_id=creator.id,
        role="ADMIN",
        title="Creator",
        status="ACTIVE",
        private_settings={}
    )
    # 5. Create the Group Wallet
    from app.models.group.wallet import GroupWallet
    new_wallet = GroupWallet(group_id=new_group_id)
    session.add(new_wallet)
    
    session.commit()
    session.refresh(new_group)
    
    return {
        "status": "success",
        "message": "Group created successfully",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name
        }
    }
