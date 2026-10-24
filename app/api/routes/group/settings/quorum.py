import math
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupGovernanceSettings, GroupVisibilitySettings
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Approval Quorum Settings"])


class UpdateQuorumSettingsRequest(BaseModel):
    # Minimum participation percentage (accepts integer e.g. 60 or string "60%")
    quorum_percentage: Optional[int | str] = Field(
        default=None,
        description="Minimum participation percentage (e.g. 60 or '60%')"
    )
    approval_strategy: Optional[str] = Field(
        default=None,
        description="Voting strategy (e.g. 'Majority Vote', 'Supermajority', 'Unanimous')"
    )
    enable_quorum_decay: Optional[bool] = Field(
        default=None,
        description="Enable Time-Locked Quorum Decay to prevent stalled votes"
    )
    quorum_decay_hours: Optional[int] = Field(
        default=None,
        ge=1,
        description="Hours of inactivity before required approvals decay"
    )
    quorum_decay_minimum_approvals: Optional[int] = Field(
        default=None,
        ge=1,
        description="The absolute floor that quorum can decay to"
    )


def _parse_pct(pct_val: int | str) -> int:
    if isinstance(pct_val, int):
        return min(max(pct_val, 1), 100)
    cleaned = str(pct_val).replace("%", "").strip()
    try:
        return min(max(int(cleaned), 1), 100)
    except ValueError:
        return 60


@router.get(
    "/{group_id}/settings/quorum",
    summary="Get Approval Quorum & Voting Requirements",
    description="Returns current minimum participation percentage, eligible member counts, and calculated minimum votes."
)
def get_quorum_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be an active member of this group to view quorum settings."
        )

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    gov = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()
    if not gov:
        gov = GroupGovernanceSettings(group_id=group_id)
        session.add(gov)
        session.commit()
        session.refresh(gov)

    # Count active eligible voting members
    total_eligible = len(session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE"
        )
    ).all())
    if total_eligible == 0:
        total_eligible = group.member_count or 1

    pct_int = _parse_pct(gov.quorum_percentage)
    min_votes = max(1, math.ceil((pct_int / 100.0) * total_eligible))

    example_text = (
        f"If set to {pct_int}%, at least {min_votes} of {total_eligible} "
        f"eligible members must cast a vote for any resolution to pass."
    )

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "group_name": getattr(group, "name", "Savings Group"),
            "quorum_percentage": pct_int,
            "quorum_percentage_display": f"{pct_int}%",
            "minimum_participation": f"{pct_int}%",
            "total_eligible_members": total_eligible,
            "minimum_votes_required": min_votes,
            "approval_strategy": gov.approval_strategy,
            "example_text": example_text,
            "enable_quorum_decay": gov.enable_quorum_decay,
            "quorum_decay_hours": gov.quorum_decay_hours,
            "quorum_decay_minimum_approvals": gov.quorum_decay_minimum_approvals,
            "allowed_options": [50, 60, 66, 75, 80, 100]
        }
    }


@router.patch(
    "/{group_id}/settings/quorum",
    summary="Update Approval Quorum & Minimum Participation",
    description="Updates the voting quorum percentage and deadlock decay rules. Restricted to Group Admin."
)
def update_quorum_settings(
    group_id: str,
    request: UpdateQuorumSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not admin_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Group Admin can update approval quorum settings."
        )

    gov = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id).with_for_update()
    ).first()
    if not gov:
        raise HTTPException(status_code=404, detail="Governance settings not found.")

    if request.quorum_percentage is not None:
        pct_int = _parse_pct(request.quorum_percentage)
        gov.quorum_percentage = f"{pct_int}%"

    if request.approval_strategy is not None:
        gov.approval_strategy = request.approval_strategy

    if request.enable_quorum_decay is not None:
        gov.enable_quorum_decay = request.enable_quorum_decay

    if request.quorum_decay_hours is not None:
        gov.quorum_decay_hours = request.quorum_decay_hours

    if request.quorum_decay_minimum_approvals is not None:
        gov.quorum_decay_minimum_approvals = request.quorum_decay_minimum_approvals

    session.add(gov)

    AuditService.record_event(
        session=session,
        action="APPROVAL_QUORUM_UPDATED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={
            "updated_by": str(current_user.id),
            "quorum_percentage": gov.quorum_percentage,
            "enable_quorum_decay": gov.enable_quorum_decay
        },
        actor_user_id=current_user.id
    )

    session.commit()
    session.refresh(gov)

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    total_eligible = len(session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE"
        )
    ).all())
    pct_int = _parse_pct(gov.quorum_percentage)
    min_votes = max(1, math.ceil((pct_int / 100.0) * total_eligible))

    return {
        "status": "success",
        "message": "Approval quorum settings updated successfully.",
        "data": {
            "group_id": group_id,
            "quorum_percentage": pct_int,
            "quorum_percentage_display": f"{pct_int}%",
            "minimum_participation": f"{pct_int}%",
            "total_eligible_members": total_eligible,
            "minimum_votes_required": min_votes,
            "approval_strategy": gov.approval_strategy,
            "example_text": f"If set to {pct_int}%, at least {min_votes} of {total_eligible} eligible members must cast a vote for any resolution to pass."
        }
    }
