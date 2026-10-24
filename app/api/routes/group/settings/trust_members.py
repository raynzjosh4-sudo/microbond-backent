from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation
from app.models.group.settings import GroupGovernanceSettings, GroupVisibilitySettings
from app.models.group.finance.guarantor_pledge import GuarantorPledge
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Trust & Members Settings"])


class UpdateTrustMembersRequest(BaseModel):
    require_guarantors: Optional[bool] = Field(
        default=None,
        description="Require a guarantor before selected benefits or loans are available"
    )
    guarantor_count: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Number of required guarantors per member"
    )
    vis_guarantor_required: Optional[bool] = Field(
        default=None,
        description="Whether regular members can see guarantor requirement rules"
    )
    minimum_trust_score: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Minimum trust score threshold required to qualify for payouts/loans"
    )


import json
from app.core.microbond_core import calculate_single_health_grade, evaluate_benefit_eligibility


def _compute_health_summary(session: Session, group_id: str) -> Dict[str, Any]:
    """
    Calculates real-time group health metrics by delegating to the authoritative
    Rust microbond_core domain engine (microbond_core/src/health_scoring.rs).
    """
    members = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE"
        )
    ).all()

    total_active_members = len(members)
    total_trust_score = sum(m.group_trust_score for m in members if m.group_trust_score is not None)
    scored_members = sum(1 for m in members if m.group_trust_score is not None)
    avg_trust = round(total_trust_score / scored_members, 1) if scored_members > 0 else 100.0

    obligations = session.exec(
        select(MemberObligation).where(MemberObligation.group_id == group_id)
    ).all()

    on_time_count = sum(1 for o in obligations if o.status == "PAID")
    default_count = sum(1 for o in obligations if o.status == "DEFAULTED")
    late_count = sum(1 for o in obligations if o.status == "LATE")
    total_defaulted_amount = sum(getattr(o, "amount", 0) for o in obligations if o.status == "DEFAULTED")
    total_expected_amount = sum(getattr(o, "amount", 0) for o in obligations)

    arrears_user_ids = {o.user_id for o in obligations if o.status in ("LATE", "DEFAULTED")}
    members_in_arrears = len(arrears_user_ids)

    # Authoritative Rust engine execution (microbond_core)
    raw_res = calculate_single_health_grade(
        group_id=group_id,
        on_time_count=on_time_count,
        late_count=late_count,
        default_count=default_count,
        total_defaulted_amount_minor=int(total_defaulted_amount),
        total_expected_amount_minor=int(total_expected_amount),
        members_in_arrears_count=members_in_arrears,
        total_active_members=max(1, total_active_members),
    )
    result = json.loads(raw_res)

    grade = result.get("grade", "A+")
    risk_tier = result.get("risk_tier", "LOW")
    status_text = "Excellent Standing" if grade == "A+" else (
        "Good Standing" if grade in ("A", "B") else (
            "Needs Improvement" if grade == "C" else "High Risk"
        )
    )

    rating_display = "Good" if grade in ("A+", "A", "B") else (
        "Fair" if grade == "C" else "At Risk"
    )

    return {
        "rating": rating_display,
        "grade": grade,
        "risk_tier": risk_tier,
        "status": status_text,
        "on_time_rate": f"{int(result.get('on_time_repayment_rate_pct', 100))}%",
        "default_rate": f"{int(result.get('default_rate_pct', 0))}%",
        "composite_score": result.get("composite_score", 100),
        "average_trust_score": f"{int(avg_trust)}/100"
    }


@router.get(
    "/{group_id}/settings/trust-members",
    summary="Get Trust & Members Settings",
    description="Returns group health rating, vouching stats, guarantor requirements, and member privacy."
)
@router.get(
    "/{group_id}/settings/trust",
    include_in_schema=False
)
def get_trust_members_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")

    is_admin = (membership.role == "ADMIN")

    gov = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()
    if not gov:
        gov = GroupGovernanceSettings(group_id=group_id)
        session.add(gov)
        session.commit()
        session.refresh(gov)

    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    if not vis:
        vis = GroupVisibilitySettings(group_id=group_id)
        session.add(vis)
        session.commit()
        session.refresh(vis)

    # 1. Group health stats
    health = _compute_health_summary(session, group_id)

    # 2. Vouching stats for current user
    my_pledges_given = session.exec(
        select(GuarantorPledge).where(
            GuarantorPledge.group_id == group_id,
            GuarantorPledge.guarantor_user_id == current_user.id,
            GuarantorPledge.status == "ACTIVE"
        )
    ).all()
    my_pledges_received = session.exec(
        select(GuarantorPledge).where(
            GuarantorPledge.group_id == group_id,
            GuarantorPledge.borrower_user_id == current_user.id,
            GuarantorPledge.status == "ACTIVE"
        )
    ).all()

    response_data = {
        "group_id": group_id,
        "group_name": getattr(group, "name", "Group"),
        "group_health_rating": health["rating"],
        "group_health_grade": health["grade"],
        "group_health_status": health["status"],
        "health_metrics": {
            "on_time_repayment_rate": health["on_time_rate"],
            "active_default_rate": health["default_rate"],
            "average_trust_score": health["average_trust_score"]
        },
        "vouching_summary": {
            "vouches_given_count": len(my_pledges_given),
            "vouches_received_count": len(my_pledges_received),
            "vouch_action_subtitle": "Submit or review a member endorsement."
        },
        "require_guarantors": gov.require_guarantors,
        "guarantor_count": gov.guarantor_count,
        "minimum_trust_score": gov.minimum_trust_score,
        "vis_guarantor_required": vis.vis_guarantor_required,
        "visibility_label": "Visible to all" if vis.vis_guarantor_required else "Hidden from members",
        "is_admin": is_admin
    }

    # Evaluate personal benefit eligibility using the Rust engine
    user_trust = membership.group_trust_score or 100
    eligibility_raw = evaluate_benefit_eligibility(
        require_guarantors=gov.require_guarantors,
        required_guarantors_count=gov.guarantor_count,
        active_guarantors_count=len(my_pledges_received),
        trust_score=user_trust,
        minimum_trust_score=gov.minimum_trust_score,
    )
    response_data["my_benefit_eligibility"] = json.loads(eligibility_raw)

    # Privacy mask: if not admin and visibility is turned off, hide guarantor details from regular members
    if not is_admin and not vis.vis_guarantor_required:
        response_data["require_guarantors"] = False

    return {
        "status": "success",
        "data": response_data
    }


@router.patch(
    "/{group_id}/settings/trust-members",
    summary="Update Trust & Members Settings",
    description="Updates guarantor requirement and member visibility toggle. Restricted to Group Admin."
)
@router.patch(
    "/{group_id}/settings/trust",
    include_in_schema=False
)
def update_trust_members_settings(
    group_id: str,
    request: UpdateTrustMembersRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update trust and membership settings.")

    gov = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id).with_for_update()
    ).first()
    if not gov:
        gov = GroupGovernanceSettings(group_id=group_id)

    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id).with_for_update()
    ).first()
    if not vis:
        vis = GroupVisibilitySettings(group_id=group_id)

    # 1. Update Governance rules
    if request.require_guarantors is not None:
        gov.require_guarantors = request.require_guarantors

    if request.guarantor_count is not None:
        gov.guarantor_count = request.guarantor_count

    if request.minimum_trust_score is not None:
        gov.minimum_trust_score = request.minimum_trust_score

    # 2. Update Visibility rules
    if request.vis_guarantor_required is not None:
        vis.vis_guarantor_required = request.vis_guarantor_required

    session.add(gov)
    session.add(vis)

    AuditService.record_event(
        session=session,
        action="TRUST_MEMBERS_SETTINGS_UPDATED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={
            "updated_by": str(current_user.id),
            "require_guarantors": gov.require_guarantors,
            "guarantor_count": gov.guarantor_count,
            "vis_guarantor_required": vis.vis_guarantor_required,
            "minimum_trust_score": gov.minimum_trust_score
        },
        actor_user_id=current_user.id
    )

    session.commit()
    session.refresh(gov)
    session.refresh(vis)

    health = _compute_health_summary(session, group_id)

    return {
        "status": "success",
        "message": "Trust & members settings updated successfully.",
        "data": {
            "group_id": group_id,
            "group_name": getattr(group, "name", "Group"),
            "group_health_rating": health["rating"],
            "require_guarantors": gov.require_guarantors,
            "guarantor_count": gov.guarantor_count,
            "minimum_trust_score": gov.minimum_trust_score,
            "vis_guarantor_required": vis.vis_guarantor_required,
            "visibility_label": "Visible to all" if vis.vis_guarantor_required else "Hidden from members"
        }
    }
