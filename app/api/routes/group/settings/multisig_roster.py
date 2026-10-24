from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupGovernanceSettings
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Multisig Roster Settings"])


class UpdateMultisigRosterRequest(BaseModel):
    required_approvals: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of approvals required (e.g. 3 of 5)"
    )
    signer_user_ids: Optional[List[str]] = Field(
        default=None,
        description="Complete list of member user IDs who are authorized signers"
    )


class SignerMemberInfo(BaseModel):
    user_id: str
    full_name: str
    phone_number: str
    role: str
    is_signer: bool
    profile_picture_url: Optional[str] = None


@router.get("/{group_id}/settings/multisig-roster", summary="Get Multisig Roster and Signers")
def get_multisig_roster(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the current multisig configuration:
    - Required approvals (e.g. 3)
    - Total signers (e.g. 5)
    - Formatted display (e.g. '3 of 5 Signers')
    - Active authorized signers roster
    - Other group members eligible to become signers
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")

    gov = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()
    if not gov:
        gov = GroupGovernanceSettings(group_id=group_id)
        session.add(gov)
        session.commit()
        session.refresh(gov)

    # Fetch all members of the group
    all_memberships = session.exec(
        select(GroupMembership, User)
        .join(User, GroupMembership.user_id == User.id)
        .where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE"
        )
    ).all()

    signers: List[dict] = []
    eligible_members: List[dict] = []

    for mem, u in all_memberships:
        member_data = {
            "user_id": str(u.id),
            "full_name": u.full_name or "Unknown Member",
            "phone_number": u.phone_number or "",
            "role": mem.role,
            "is_signer": bool(mem.is_signer),
            "profile_picture_url": u.profile_picture_url,
        }
        if mem.is_signer:
            signers.append(member_data)
        else:
            eligible_members.append(member_data)

    total_signers = len(signers)
    required = gov.multi_sig_required_approvals

    # Ensure required does not exceed total signers in display
    if total_signers > 0 and required > total_signers:
        required = total_signers

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "require_multi_signature": gov.require_multi_signature,
            "required_approvals": required,
            "total_signers": total_signers,
            "display": f"{required} of {total_signers} Signers",
            "signers": signers,
            "eligible_members": eligible_members,
            "all_members_count": len(all_memberships)
        }
    }


@router.patch("/{group_id}/settings/multisig-roster", summary="Update Multisig Approvals or Roster")
def update_multisig_roster(
    group_id: str,
    request: UpdateMultisigRosterRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the required approvals threshold and/or the full list of authorized signers.
    Only the Group Admin can perform this operation.
    """
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can manage the multisig roster.")

    gov = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id).with_for_update()
    ).first()
    if not gov:
        raise HTTPException(status_code=404, detail="Governance settings not found.")

    all_members = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE"
        )
    ).all()
    valid_user_ids = {str(m.user_id) for m in all_members}

    # 1. If signer roster is provided, update everyone's is_signer flag
    if request.signer_user_ids is not None:
        for uid in request.signer_user_ids:
            if uid not in valid_user_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"User {uid} is not an active member of this group."
                )

        if len(request.signer_user_ids) == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one signer must be designated."
            )

        for m in all_members:
            m.is_signer = str(m.user_id) in request.signer_user_ids
            session.add(m)

        new_total_signers = len(request.signer_user_ids)
        target_approvals = request.required_approvals if request.required_approvals is not None else gov.multi_sig_required_approvals
        if target_approvals > new_total_signers:
            raise HTTPException(
                status_code=400,
                detail=f"Required approvals ({target_approvals}) cannot exceed total signers ({new_total_signers})."
            )
        gov.multi_sig_required_approvals = target_approvals

    # 2. If only required_approvals was updated
    elif request.required_approvals is not None:
        current_signers_count = sum(1 for m in all_members if m.is_signer)
        if current_signers_count == 0:
            current_signers_count = 1  # Fallback

        if request.required_approvals > current_signers_count:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot require {request.required_approvals} approvals when there are only {current_signers_count} designated signers."
            )
        gov.multi_sig_required_approvals = request.required_approvals

    session.add(gov)

    # Record tamper-evident audit log
    AuditService.record_event(
        session=session,
        action="MULTISIG_ROSTER_UPDATED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={
            "updated_by": str(current_user.id),
            "required_approvals": gov.multi_sig_required_approvals,
            "signer_count": len(request.signer_user_ids) if request.signer_user_ids is not None else None
        },
        actor_user_id=current_user.id
    )

    session.commit()
    session.refresh(gov)

    current_signers = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.is_signer == True,
            GroupMembership.status == "ACTIVE"
        )
    ).all()
    total_signers = len(current_signers)

    return {
        "status": "success",
        "message": "Multisig roster and required approvals updated successfully.",
        "data": {
            "group_id": group_id,
            "required_approvals": gov.multi_sig_required_approvals,
            "total_signers": total_signers,
            "display": f"{gov.multi_sig_required_approvals} of {total_signers} Signers"
        }
    }


@router.post("/{group_id}/settings/multisig-roster/signers/{user_id}", summary="Add Signer to Multisig Roster")
def add_signer_to_roster(
    group_id: str,
    user_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Designates a single member as an authorized cryptographic signer.
    """
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can add signers.")

    target_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not target_membership:
        raise HTTPException(status_code=404, detail="Member not found in this group.")

    target_membership.is_signer = True
    session.add(target_membership)

    AuditService.record_event(
        session=session,
        action="SIGNER_ADDED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={"signer_user_id": user_id, "added_by": str(current_user.id)},
        actor_user_id=current_user.id
    )
    session.commit()

    # Recount total signers
    signers_count = len(session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.is_signer == True,
            GroupMembership.status == "ACTIVE"
        )
    ).all())

    gov = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()
    required = gov.multi_sig_required_approvals if gov else 1

    return {
        "status": "success",
        "message": "Member successfully designated as an authorized signer.",
        "data": {
            "group_id": group_id,
            "user_id": user_id,
            "is_signer": True,
            "total_signers": signers_count,
            "display": f"{required} of {signers_count} Signers"
        }
    }


@router.delete("/{group_id}/settings/multisig-roster/signers/{user_id}", summary="Remove Signer from Multisig Roster")
def remove_signer_from_roster(
    group_id: str,
    user_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Revokes signer status from a member.
    Automatically prevents removing signers if it would drop total signers below required approvals,
    or adjusts required approvals down safely.
    """
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can remove signers.")

    target_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not target_membership:
        raise HTTPException(status_code=404, detail="Member not found in this group.")

    # Count signers
    all_signers = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.is_signer == True,
            GroupMembership.status == "ACTIVE"
        )
    ).all()

    if len(all_signers) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove the last remaining signer. The group must have at least one authorized signer."
        )

    target_membership.is_signer = False
    session.add(target_membership)

    gov = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()

    remaining_signers = len(all_signers) - 1
    if gov and gov.multi_sig_required_approvals > remaining_signers:
        # Automatically lower required approvals to remaining signers
        gov.multi_sig_required_approvals = remaining_signers
        session.add(gov)

    AuditService.record_event(
        session=session,
        action="SIGNER_REMOVED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={"removed_signer_id": user_id, "removed_by": str(current_user.id)},
        actor_user_id=current_user.id
    )
    session.commit()

    required = gov.multi_sig_required_approvals if gov else 1

    return {
        "status": "success",
        "message": "Signer status revoked successfully.",
        "data": {
            "group_id": group_id,
            "user_id": user_id,
            "is_signer": False,
            "total_signers": remaining_signers,
            "required_approvals": required,
            "display": f"{required} of {remaining_signers} Signers"
        }
    }
