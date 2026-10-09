from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
import uuid

from app.core.database import get_session
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.models.group.settings import GroupSettings
from app.models.group.long_term import TargetSavingsGroupDetails
from app.schemas.target_savings_group_create_request import TargetSavingsGroupCreateRequest

router = APIRouter(prefix="/api/v1/groups/target-savings", tags=["Target Savings Groups"])

@router.post("/create")
def create_group(request: TargetSavingsGroupCreateRequest, session: Session = Depends(get_session)):
    # 1. Authenticate / Find creator user
    creator = session.query(User).filter(User.phone_number == request.created_by_phone).first()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator user not found")
        
    # Example logic: require KYC Tier 2 for group creation
    if creator.kyc_tier < 2:
        raise HTTPException(
            status_code=403, 
            detail="Creator must have an independent, Tier 2 verified National ID profile."
        )
        
    # Example logic: require Trust Score >= 80 for advanced groups
    if creator.trust_score < 80:
        raise HTTPException(
            status_code=403, 
            detail="Trust Score of 80+ is required to initiate savings groups."
        )

    # 2. Generate unique IDs
    new_group_id = str(uuid.uuid4())
    invite_code = str(uuid.uuid4())[:8].upper()
    
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
        member_count=1 # Creator is the first member
    )
    session.add(new_group)
    
    # 3b. Create Group Settings separately
    new_settings = GroupSettings(
        group_id=new_group_id
    )
    session.add(new_settings)
    
    # 3c. Save Target Savings Details
    target_details = TargetSavingsGroupDetails(
        group_id=new_group_id,
        goal_amount=request.goal_amount,
        target_date=request.target_date,
        savings_pace=request.savings_pace,
        lock_funds=request.lock_funds,
        hide_leaderboard=request.hide_leaderboard,
        allow_early_exits=request.allow_early_exits,
        overage_policy=request.overage_policy,
        top_up_matching_amount=request.top_up_matching_amount,
        progress_percent=0.0
    )
    session.add(target_details)
    
    # 4. Create the Membership for the Creator (as ADMIN)
    new_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=new_group_id,
        user_id=creator.id,
        role="ADMIN",
        joined_at=int(uuid.uuid1().time) # roughly timestamp
    )
    session.add(new_membership)
    
    # 5. Commit all changes atomically
    try:
        session.commit()
        session.refresh(new_group)
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    return {
        "status": "success",
        "message": "Target Savings Group created successfully",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "goal_amount": target_details.goal_amount,
            "target_date": target_details.target_date
        }
    }
