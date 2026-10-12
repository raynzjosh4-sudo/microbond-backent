from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupGovernanceSettings
from app.models.group.rotating import RotatingGroupDetails
from app.core.firebase_config import send_push_notification
from pydantic import BaseModel, Field
from typing import Optional
import uuid

router = APIRouter(prefix="/api/v1/groups/join", tags=["Group Join Requests"])

class GroupJoinRequest(BaseModel):
    group_id: Optional[str] = Field(default=None, description="The UUID of the group (used for public groups)")
    invite_code: Optional[str] = Field(default=None, description="The unique 8-character invite code (used for private groups)")
    guarantor_ids: Optional[list[str]] = Field(default_factory=list, description="List of UUIDs of active group members vouching for this user")

@router.post("/")
def join_group(
    request: GroupJoinRequest, 
    session: Session = Depends(get_session), 
    current_user: User = Depends(get_current_user)
):
    if not request.group_id and not request.invite_code:
        raise HTTPException(status_code=400, detail="Must provide either group_id or invite_code.")

    # 1. Base Authentication & Group Lookup (With Row-Level Lock to prevent race conditions)
    if request.invite_code:
        group = session.query(Group).filter(Group.invite_code == request.invite_code).with_for_update().first()
        if not group:
            raise HTTPException(status_code=404, detail="Invalid invite code.")
    else:
        group = session.query(Group).filter(Group.group_id == request.group_id).with_for_update().first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found.")
        if group.visibility == "PRIVATE":
            raise HTTPException(status_code=403, detail="This is a private group. You must use an invite code to join.")
        
    existing_membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group.group_id,
        GroupMembership.user_id == current_user.id
    ).first()
    if existing_membership:
        raise HTTPException(status_code=400, detail="You are already in this group or have a pending request.")
        
    if group.max_members and group.member_count >= group.max_members:
        raise HTTPException(status_code=400, detail="This group has reached its maximum capacity.")

    settings = session.query(GroupGovernanceSettings).filter(GroupGovernanceSettings.group_id == group.group_id).first()

    # 4. Execute all the rigorous cross-group risk checks via the centralized risk engine
    from app.services.group_risk import check_user_join_eligibility
    check_user_join_eligibility(current_user, group, settings, session, guarantor_ids=request.guarantor_ids)

    # ==========================================
    # 🏁 FINALIZE JOIN REQUEST
    # ==========================================
    # Order of strictness: Guarantor Consent > Admin Approval > Instant Join
    if settings.require_guarantors and request.guarantor_ids:
        final_status = "PENDING_GUARANTOR"
    elif settings.requires_admin_approval:
        final_status = "PENDING_APPROVAL"
    else:
        final_status = "ACTIVE"
    
    new_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group.group_id,
        user_id=current_user.id,
        role="MEMBER",
        title="Member",
        status=final_status,
        private_settings={}
    )
    session.add(new_membership)
    
    # ==========================================
    # 🤝 BIND THE GUARANTOR PLEDGES
    # ==========================================
    if settings.require_guarantors and request.guarantor_ids:
        from app.models.group.finance import GuarantorPledge
        
        # Calculate max liability per guarantor
        pledge_liability = 0.0
        if group.type == "MERRY_GO_ROUND":
            rotating_details = session.query(RotatingGroupDetails).filter(RotatingGroupDetails.group_id == group.group_id).first()
            if rotating_details:
                # Distribute the total liability across the number of required guarantors
                total_liability = rotating_details.contribution_amount * rotating_details.number_of_cycles
                pledge_liability = total_liability / len(request.guarantor_ids)
                
        for gid in request.guarantor_ids:
            new_pledge = GuarantorPledge(
                group_id=group.group_id,
                guarantor_user_id=gid,
                borrower_user_id=current_user.id,
                maximum_liability_amount=pledge_liability, 
                status="PENDING_CONSENT" # The Guarantor MUST accept this before the user is let in
            )
            session.add(new_pledge)
    
    if final_status == "ACTIVE":
        group.member_count += 1
        
    session.commit()

    # ── Push: notify admins that a join request is waiting for approval ──────
    if final_status == "PENDING_APPROVAL":
        admin_memberships = session.exec(
            select(GroupMembership).where(
                GroupMembership.group_id == group.group_id,
                GroupMembership.role == "ADMIN",
                GroupMembership.status == "ACTIVE"
            )
        ).all()
        admin_users = session.exec(
            select(User).where(User.id.in_([m.user_id for m in admin_memberships]))
        ).all()
        for admin in admin_users:
            if admin.fcm_token:
                send_push_notification(
                    token=admin.fcm_token,
                    title="New Join Request 🙋",
                    body=f"{current_user.full_name} wants to join '{group.name}'. Tap to review.",
                    data={"type": "JOIN_REQUEST_PENDING", "group_id": group.group_id}
                )

    # ── Push: notify each guarantor that their consent is required ───────────
    if settings.require_guarantors and request.guarantor_ids:
        for gid in request.guarantor_ids:
            try:
                guarantor = session.get(User, uuid.UUID(gid))
                if guarantor and guarantor.fcm_token:
                    send_push_notification(
                        token=guarantor.fcm_token,
                        title="Guarantor Request 🤝",
                        body=f"{current_user.full_name} listed you as a guarantor to join '{group.name}'. Tap to review.",
                        data={"type": "GUARANTOR_REQUEST", "group_id": group.group_id}
                    )
            except Exception:
                pass

    return {
        "status": "success",
        "message": "Joined successfully!" if final_status == "ACTIVE" else "Join request sent for approval.",
        "membership_status": final_status,
        "group_id": group.group_id
    }
