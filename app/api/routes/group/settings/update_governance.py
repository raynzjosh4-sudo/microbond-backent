from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupGovernanceSettings
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateGovernanceSettingsRequest(BaseModel):
    require_multi_signature: Optional[bool] = None
    multi_sig_required_approvals: Optional[int] = None
    quorum_percentage: Optional[str] = None
    designated_signer_ids: Optional[List[str]] = None
    require_guarantors: Optional[bool] = None
    guarantor_count: Optional[int] = None
    group_charter_url: Optional[str] = None
    is_audit_active: Optional[bool] = None

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

    if request.is_audit_active is not None:
        settings.is_audit_active = request.is_audit_active

    session.add(settings)
    session.commit()
    session.refresh(settings)
    return {"status": "success", "message": "Governance & multi-sig settings updated.", "data": settings.dict(exclude={"id", "group_id"})}


@router.post("/{group_id}/settings/governance/audit/start", summary="Start New Financial Audit")
def start_financial_audit(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Initiates a new deep-dive financial audit review for the group.
    Sets is_audit_active to True and records an immutable audit event.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can initiate a financial audit.")

    settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()
    if not settings:
        raise HTTPException(status_code=404, detail="Governance settings not found.")

    settings.is_audit_active = True
    session.add(settings)

    # Record tamper-evident audit event
    AuditService.record_event(
        session=session,
        action="AUDIT_INITIATED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={"initiated_by": str(current_user.id), "group_id": group_id},
        actor_user_id=current_user.id
    )
    session.commit()

    return {
        "status": "success",
        "message": "Deep-dive financial audit initiated. Ledger records are under active review.",
        "data": {
            "group_id": group_id,
            "is_audit_active": True,
            "audit_status": "Healthy",
            "audit_status_title": "Active Audit In Progress",
            "audit_status_description": "Deep-dive review of group transactions is underway. Records verified."
        }
    }


@router.post("/{group_id}/settings/governance/audit/complete", summary="Complete Active Financial Audit")
def complete_financial_audit(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Marks the active financial audit as complete and clear.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can close an audit.")

    settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()
    if not settings:
        raise HTTPException(status_code=404, detail="Governance settings not found.")

    settings.is_audit_active = False
    session.add(settings)

    AuditService.record_event(
        session=session,
        action="AUDIT_COMPLETED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={"completed_by": str(current_user.id), "status": "VERIFIED_AND_CLEAR"},
        actor_user_id=current_user.id
    )
    session.commit()

    return {
        "status": "success",
        "message": "Financial audit completed and verified clear.",
        "data": {
            "group_id": group_id,
            "is_audit_active": False,
            "audit_status": "Healthy",
            "audit_status_title": "No Active Audit",
            "audit_status_description": "The group's financial records are currently verified and clear."
        }
    }
