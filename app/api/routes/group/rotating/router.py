from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlmodel import Session
import uuid
import time

from app.core.database import get_session
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User

router = APIRouter(prefix="/api/v1/groups/rotating", tags=["Rotating Groups"])

from app.schemas.rotating_group_create_request import RotatingGroupCreateRequest
@router.post("/create")
def create_group(request: RotatingGroupCreateRequest, session: Session = Depends(get_session)):
    # 1. Authenticate / Find creator user
    creator = session.query(User).filter(User.phone_number == request.created_by_phone).first()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator user not found")
        
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
    from app.models.group.settings import GroupSettings
    new_settings = GroupSettings(
        group_id=new_group_id,
        enable_late_fees=request.enable_late_fees,
        late_fee_amount=request.late_fee_amount,
        late_fee_frequency=request.late_fee_frequency,
        enable_grace_period=request.enable_grace_period,
        grace_period_duration=request.grace_period_duration
    )
    session.add(new_settings)
    
    # 3c. If this is a Rotating Group, calculate cycles and save details
    if request.type == "MERRY_GO_ROUND":
        import math
        from app.models.group.rotating import RotatingGroupDetails
        
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
                
        rotating_details = RotatingGroupDetails(
            group_id=new_group_id,
            contribution_amount=request.contribution_amount,
            payouts_per_cycle=request.payouts_per_cycle,
            number_of_cycles=calculated_cycles,
            collection_days_interval=request.collection_days_interval,
            group_start_time=request.group_start_time,
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
    session.add(new_membership)
    
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
