from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional, Dict, Any

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import (
    GroupGovernanceSettings,
    GroupVisibilitySettings
)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

@router.get("/{group_id}/settings/governance", summary="Get Governance Rules (Privacy-Gated)")
def get_governance_settings(
    group_id: str, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the Governance Rules for the group. 
    If the requester is a regular member, the response is dynamically stripped
    based on the Admin's visibility toggles.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="You must be a member to view settings.")
        
    is_admin = membership.role == "ADMIN"
    
    gov_settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()
    
    vis_settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    
    if not gov_settings or not vis_settings:
        raise HTTPException(status_code=404, detail="Settings not found.")
        
    # Convert settings to dictionary to easily pop hidden keys
    response_data = gov_settings.dict(exclude={"id", "group_id", "updated_at"})
    
    # If the user is NOT an Admin, apply the privacy strips!
    if not is_admin:
        if not vis_settings.vis_require_multi_signature:
            response_data.pop("require_multi_signature", None)
            response_data.pop("multi_sig_required_approvals", None)
            
        if not vis_settings.vis_approval_quorum:
            response_data.pop("approval_strategy", None)
            response_data.pop("quorum_percentage", None)
            
        if not vis_settings.vis_active_audit_status:
            response_data.pop("is_audit_active", None)
            
        if not vis_settings.vis_guarantor_required:
            response_data.pop("require_guarantors", None)
            response_data.pop("guarantor_count", None)
            
        # The other visibility toggles (multi_signature_roster, pending_payout_queue, time_lock_disbursals)
        # affect other specific feature APIs (like the payout queue API or roster API), but any 
        # related basic settings we have in the governance model are hidden here.
            
    return {"status": "success", "data": response_data}
