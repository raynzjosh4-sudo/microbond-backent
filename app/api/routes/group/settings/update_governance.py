from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupGovernanceSettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateGovernanceSettingsRequest(BaseModel):
    require_multi_signature: Optional[bool] = None
    multi_sig_required_approvals: Optional[int] = None
    quorum_percentage: Optional[str] = None
    designated_signer_ids: Optional[List[str]] = None
    require_guarantors: Optional[bool] = None
    guarantor_count: Optional[int] = None
    group_charter_url: Optional[str] = None

@router.patch("/{group_id}/settings/governance", summary="Admin: Update Governance & Multi-Sig Settings")
def update_governance_settings(
    group_id: str, 
    request: UpdateGovernanceSettingsRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Verify Admin Access
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()
    
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update governance settings.")

    # Get Governance Settings
    settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Governance settings not found.")

    if request.require_multi_signature is not None:
        settings.require_multi_signature = request.require_multi_signature
        
    if request.quorum_percentage is not None:
        settings.quorum_percentage = request.quorum_percentage
        
    if request.require_guarantors is not None:
        settings.require_guarantors = request.require_guarantors
        
    if request.guarantor_count is not None:
        settings.guarantor_count = request.guarantor_count
        
    if request.group_charter_url is not None:
        settings.group_charter_url = request.group_charter_url

    # Apply Roster & Approvals
    if request.designated_signer_ids is not None:
        # Validate that these users are actually in the group
        memberships = session.exec(
            select(GroupMembership).where(GroupMembership.group_id == group_id)
        ).all()
        
        valid_user_ids = {str(m.user_id) for m in memberships}
        for signer_id in request.designated_signer_ids:
            if signer_id not in valid_user_ids:
                raise HTTPException(
                    status_code=400, 
                    detail=f"User {signer_id} cannot be a signer because they are not a member of the group."
                )

        # Update the is_signer flag for everyone
        for m in memberships:
            m.is_signer = str(m.user_id) in request.designated_signer_ids
            session.add(m)

        total_signers = len(request.designated_signer_ids)
        
        # If they also passed multi_sig_required_approvals, validate it against the new roster
        required_approvals = request.multi_sig_required_approvals if request.multi_sig_required_approvals is not None else settings.multi_sig_required_approvals
        
        if required_approvals > total_signers:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot require {required_approvals} approvals when there are only {total_signers} designated signers."
            )
            
        if request.multi_sig_required_approvals is not None:
            settings.multi_sig_required_approvals = request.multi_sig_required_approvals
            
    else:
        # If they didn't pass a new roster, but passed a new approval count, validate it against the EXISTING roster
        if request.multi_sig_required_approvals is not None:
            current_signers_count = session.exec(
                select(GroupMembership).where(
                    GroupMembership.group_id == group_id,
                    GroupMembership.is_signer == True
                )
            ).all()
            
            if request.multi_sig_required_approvals > len(current_signers_count):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot require {request.multi_sig_required_approvals} approvals when there are only {len(current_signers_count)} designated signers."
                )
            settings.multi_sig_required_approvals = request.multi_sig_required_approvals

    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Governance & multi-sig settings updated."}
