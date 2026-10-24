from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from sqlmodel import Session, select
import uuid

from app.core.database import get_session
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.models.group.wallet import GroupWallet
from app.models.group.settings import (
    GroupFinancialSettings, 
    GroupGovernanceSettings, 
    GroupCommunicationSettings, 
    GroupVisibilitySettings
)
from app.api.dependencies import get_current_user
from app.api.routes.group.chat.messages import broadcast_system_message_sync

router = APIRouter(prefix="/api/v1/groups", tags=["Group Core"])

class UnifiedGroupCreateRequest(BaseModel):
    # Step 1: Basics
    name: str = Field(..., max_length=100)
    description: str = Field(default="")
    group_image_url: str = Field(default="")
    
    # Step 2: Classification
    type: str = Field(default="STANDARD", description="STANDARD, MERRY_GO_ROUND, TARGET_SAVINGS, INVESTMENT")
    payment_mode: str = Field(default="OBLIGATION", description="OBLIGATION, VOLUNTARY, MIXED")
    visibility: str = Field(default="PRIVATE")
    currency: str = Field(default="UGX")
    
    # Step 3: Rules & Caps
    max_members: Optional[int] = Field(default=None)
    
    # Financial Rules
    enable_late_fees: bool = Field(default=False)
    requires_admin_approval: bool = Field(default=True)

@router.post("/create", summary="Unified Group Creation Wizard API")
def create_unified_group(
    request: UnifiedGroupCreateRequest, 
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Handles the 10-step frontend wizard to create a group in a single atomic database transaction.
    Sets up the Group, Wallet, Settings, Membership, and injects the initialization chat message.
    """
    # 1. Enforcement / Eligibility Checks (Progressive Unlocks)
    from app.services.group.group_auth_service import (
        get_permitted_group_creation_types,
        is_unrestricted_group_creator,
        SavingsGroupType,
    )
    
    is_super = is_unrestricted_group_creator(current_user)

    # Normalize aliases if provided by frontend
    normalized_type = request.type
    if normalized_type == "TARGET_SAVINGS":
        normalized_type = "GOAL_SAVINGS"
    elif normalized_type == "ROTATING":
        normalized_type = "MERRY_GO_ROUND"

    # Try to map the string type to the Enum
    try:
        requested_type = SavingsGroupType(normalized_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid group type: {request.type}")
        
    if not is_super:
        allowed_types = get_permitted_group_creation_types(session, current_user.id)
        if requested_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You are not authorized to create a {request.type} group yet. Improve your KYC, trust score, or group health to unlock this feature."
            )
            
        # 1b. Running Group Guard — cannot create a new group while owning a group that
        #     has live funds (total_balance > 0) or active co-members, because abandoning
        #     or mis-managing a live group risks other people's pooled money.
        running_owned_groups = session.exec(
            select(Group).where(
                Group.created_by_user_id == current_user.id,
                Group.status == "ACTIVE",
                (Group.total_balance > 0) | (Group.member_count > 1)
            )
        ).all()

        if running_owned_groups:
            names = ", ".join(f"'{g.name}'" for g in running_owned_groups)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"You cannot create a new group while you are still managing a running group: {names}. "
                    "Please close or transfer ownership of your active group(s) first to protect your members' funds."
                )
            )

        # 1c. Spam / DoS Protection (Max 5 active groups per user)
        from sqlalchemy import func
        owned_groups_count = session.exec(
            select(func.count()).where(
                Group.created_by_user_id == current_user.id,
                Group.status == "ACTIVE"
            )
        ).one()
        
        if owned_groups_count >= 5:
            raise HTTPException(
                status_code=429,
                detail="You have reached the maximum limit of 5 active owned groups. Please close or delete an unused group first."
            )

    # 2. Setup Core Group with Collision-Safe Invite Code
    new_group_id = str(uuid.uuid4())
    
    # Retry loop to guarantee invite_code uniqueness
    max_retries = 5
    invite_code = None
    for _ in range(max_retries):
        candidate = str(uuid.uuid4())[:8].upper()
        existing = session.exec(select(Group).where(Group.invite_code == candidate)).first()
        if not existing:
            invite_code = candidate
            break
            
    if not invite_code:
        raise HTTPException(status_code=500, detail="Failed to generate a unique invite code. Please try again.")
    
    new_group = Group(
        group_id=new_group_id,
        name=request.name,
        description=request.description,
        group_image_url=request.group_image_url,
        type=request.type,
        payment_mode=request.payment_mode,
        visibility=request.visibility,
        currency=request.currency,
        created_by_user_id=current_user.id,
        invite_code=invite_code,
        member_count=1,
        max_members=request.max_members
    )
    session.add(new_group)
    
    # 3. Setup Default Wallets
    new_wallet = GroupWallet(group_id=new_group_id)
    session.add(new_wallet)
    
    # 4. Setup Distributed Settings Tables
    session.add(GroupFinancialSettings(group_id=new_group_id, enable_late_fees=request.enable_late_fees))
    session.add(GroupGovernanceSettings(group_id=new_group_id, requires_admin_approval=request.requires_admin_approval))
    session.add(GroupCommunicationSettings(group_id=new_group_id))
    session.add(GroupVisibilitySettings(group_id=new_group_id))
    
    # 5. Create Creator's Membership (Admin)
    new_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=new_group_id,
        user_id=current_user.id,
        role="ADMIN",
        title="Creator",
        status="ACTIVE"
    )
    session.add(new_membership)
    
    # 6. Commit Atomically
    try:
        session.commit()
        session.refresh(new_group)
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create group: {e}")
        
    # 7. Initialize Chat (Background Task)
    broadcast_system_message_sync(
        group_id=new_group_id,
        message_text=f"{current_user.full_name} created the group '{new_group.name}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Group fully initialized and created.",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name
        }
    }
