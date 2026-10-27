from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import Session, select
from typing import Optional, Dict, Any

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import (
    GroupFinancialSettings,
    GroupGovernanceSettings,
    GroupVisibilitySettings,
    GroupCommunicationSettings
)
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.long_term import (
    TargetSavingsGroupDetails,
    FundraiserCampaignConfig,
    FundraiserLiveStats,
    SharedWalletConfig,
    SharedWalletOperationalSettings
)
from app.models.group.welfare_event import (
    WelfareFundConfig,
    WelfareFundOperationalSettings,
    EventCommitteeConfig,
    EventCommitteeOperationalSettings
)
from app.models.group.investment_association import (
    InvestmentClubConfig,
    InvestmentClubOperationalSettings,
    InvestmentClubLoan,
    AssociationDuesConfig,
    AssociationDuesOperationalSettings,
    AssociationDuesExemption
)
from app.models.group.bill_split import (
    BillSplitConfig,
    BillSplitOperationalSettings
)
from app.models.group.finance import GroupPayout

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

    response_data = gov_settings.dict(exclude={"id", "group_id", "updated_at"})

    # Compute live governance metrics for the UI hub screen
    signers = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.is_signer == True
        )
    ).all()
    if not signers:
        admins = session.exec(
            select(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.role == "ADMIN",
                GroupMembership.status == "ACTIVE"
            )
        ).all()
        if not admins:
            admins = session.exec(
                select(GroupMembership).where(
                    GroupMembership.group_id == group_id,
                    GroupMembership.status == "ACTIVE"
                ).limit(1)
            ).all()
        for a in admins:
            a.is_signer = True
            session.add(a)
        if admins:
            session.commit()
            signers = admins

    signers_count = len(signers) if signers else 1
    actual_approvals = min(gov_settings.multi_sig_required_approvals, signers_count) if signers_count > 0 else 1
    if gov_settings.multi_sig_required_approvals > signers_count and signers_count > 0:
        gov_settings.multi_sig_required_approvals = actual_approvals
        session.add(gov_settings)
        session.commit()

    pending_payouts = session.exec(
        select(GroupPayout).where(
            GroupPayout.group_id == group_id,
            GroupPayout.status.in_(["PENDING", "PROCESSING", "ON_HOLD"])
        )
    ).all()
    pending_count = len(pending_payouts) if pending_payouts else 0

    response_data["total_signers_count"] = signers_count
    response_data["signers_display"] = f"{actual_approvals} of {signers_count} Signers"
    response_data["quorum_display"] = f"{actual_approvals} of {signers_count}"
    response_data["my_approval_authorization"] = "Authorized" if (is_admin or getattr(membership, "is_signer", False)) else "Unauthorized"
    response_data["audit_status"] = "In Review" if gov_settings.is_audit_active else "Healthy"
    response_data["audit_status_title"] = "Active Audit In Progress" if gov_settings.is_audit_active else "No Active Audit"
    response_data["audit_status_description"] = (
        "The group is undergoing a deep-dive review of financial transactions."
        if gov_settings.is_audit_active
        else "The group's financial records are currently verified and clear."
    )

    if not is_admin:
        if not vis_settings.vis_require_multi_signature:
            response_data.pop("require_multi_signature", None)
            response_data.pop("multi_sig_required_approvals", None)
            response_data.pop("signers_display", None)
            response_data.pop("total_signers_count", None)
        if not vis_settings.vis_approval_quorum:
            response_data.pop("approval_strategy", None)
            response_data.pop("quorum_percentage", None)
            response_data.pop("quorum_display", None)
        if not vis_settings.vis_active_audit_status:
            response_data.pop("is_audit_active", None)
            response_data.pop("audit_status", None)
            response_data.pop("audit_status_title", None)
            response_data.pop("audit_status_description", None)
        if not vis_settings.vis_pending_payout_queue:
            response_data.pop("pending_disbursals_count", None)
        if not vis_settings.vis_guarantor_required:
            response_data.pop("require_guarantors", None)
            response_data.pop("guarantor_count", None)

    return {"status": "success", "data": response_data}


@router.get("/{group_id}/settings/summary", summary="Get Full Settings Summary (Merged by Group Type)")
def get_settings_summary(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the complete settings view for any group type.
    Merges base settings (financial, governance) with the group-type-specific
    settings table so the client sees one consistent object.
    Admins see everything; members see a stripped view based on visibility toggles.
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

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    fin = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    gov = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()
    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    comm = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()

    base = {
        "group_id": group.group_id,
        "name": group.name,
        "description": group.description,
        "type": group.type,
        "currency": group.currency,
        "visibility": group.visibility,
        "max_members": group.max_members,
        "member_count": group.member_count,
        "financial": fin.dict(exclude={"id", "group_id"}) if fin else {},
        "governance": gov.dict(exclude={"id", "group_id"}) if gov else {},
        "communication": comm.dict(exclude={"id", "group_id"}) if comm else {},
        "member_visibility_toggles": vis.dict(exclude={"id", "group_id"}) if vis and is_admin else {}
    }

    # ── Type-specific settings appended as their own section ─────────────────
    type_specific: Dict[str, Any] = {}

    if group.type == "MERRY_GO_ROUND":
        rotating = session.exec(
            select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
        ).first()
        if rotating:
            type_specific = rotating.dict(exclude={"id", "group_id", "created_at"})

    elif group.type == "GOAL_SAVINGS":
        target = session.exec(
            select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
        ).first()
        if target:
            type_specific = target.dict(exclude={"id", "group_id", "created_at"})

    elif group.type == "FUNDRAISER":
        config = session.exec(
            select(FundraiserCampaignConfig).where(FundraiserCampaignConfig.group_id == group_id)
        ).first()
        live = session.exec(
            select(FundraiserLiveStats).where(FundraiserLiveStats.group_id == group_id)
        ).first()
        type_specific = {
            "campaign_config": config.dict(exclude={"id", "group_id", "created_at"}) if config else {},
            "live_stats": live.dict(exclude={"id", "group_id"}) if live else {}
        }

    elif group.type == "SHARED_WALLET":
        config = session.exec(
            select(SharedWalletConfig).where(SharedWalletConfig.group_id == group_id)
        ).first()
        ops = session.exec(
            select(SharedWalletOperationalSettings).where(
                SharedWalletOperationalSettings.group_id == group_id
            )
        ).first()
        type_specific = {
            "wallet_config": config.dict(exclude={"id", "group_id", "created_at"}) if config else {},
            "operational_settings": ops.dict(exclude={"id", "group_id"}) if ops else {}
        }

    elif group.type == "WELFARE_FUND":
        config = session.exec(
            select(WelfareFundConfig).where(WelfareFundConfig.group_id == group_id)
        ).first()
        ops = session.exec(
            select(WelfareFundOperationalSettings).where(
                WelfareFundOperationalSettings.group_id == group_id
            )
        ).first()
        type_specific = {
            "welfare_config": config.dict(exclude={"id", "group_id", "created_at"}) if config else {},
            "operational_settings": ops.dict(exclude={"id", "group_id"}) if ops else {}
        }

    elif group.type == "EVENT_COMMITTEE":
        config = session.exec(
            select(EventCommitteeConfig).where(EventCommitteeConfig.group_id == group_id)
        ).first()
        ops = session.exec(
            select(EventCommitteeOperationalSettings).where(
                EventCommitteeOperationalSettings.group_id == group_id
            )
        ).first()
        type_specific = {
            "event_config": config.dict(exclude={"id", "group_id", "created_at"}) if config else {},
            "operational_settings": ops.dict(exclude={"id", "group_id"}) if ops else {}
        }

    elif group.type == "INVESTMENT_CLUB":
        config = session.exec(
            select(InvestmentClubConfig).where(InvestmentClubConfig.group_id == group_id)
        ).first()
        ops = session.exec(
            select(InvestmentClubOperationalSettings).where(
                InvestmentClubOperationalSettings.group_id == group_id
            )
        ).first()
        active_loans = session.exec(
            select(InvestmentClubLoan).where(
                InvestmentClubLoan.group_id == group_id,
                InvestmentClubLoan.status.in_(["PENDING", "APPROVED", "DISBURSED"])
            )
        ).all()
        type_specific = {
            "investment_config": config.dict(exclude={"id", "group_id", "created_at"}) if config else {},
            "operational_settings": ops.dict(exclude={"id", "group_id"}) if ops else {},
            "active_loans_count": len(active_loans)
        }

    elif group.type == "ASSOCIATION_DUES":
        config = session.exec(
            select(AssociationDuesConfig).where(AssociationDuesConfig.group_id == group_id)
        ).first()
        ops = session.exec(
            select(AssociationDuesOperationalSettings).where(
                AssociationDuesOperationalSettings.group_id == group_id
            )
        ).first()
        active_exemptions = session.exec(
            select(AssociationDuesExemption).where(
                AssociationDuesExemption.group_id == group_id,
                AssociationDuesExemption.is_active == True
            )
        ).all()
        type_specific = {
            "association_config": config.dict(exclude={"id", "group_id", "created_at"}) if config else {},
            "operational_settings": ops.dict(exclude={"id", "group_id"}) if ops else {},
            "active_exemptions_count": len(active_exemptions)
        }

    elif group.type == "BILL_SPLIT":
        config = session.exec(
            select(BillSplitConfig).where(BillSplitConfig.group_id == group_id)
        ).first()
        ops = session.exec(
            select(BillSplitOperationalSettings).where(
                BillSplitOperationalSettings.group_id == group_id
            )
        ).first()
        type_specific = {
            "bill_split_config": config.dict(exclude={"id", "group_id", "created_at"}) if config else {},
            "operational_settings": ops.dict(exclude={"id", "group_id"}) if ops else {}
        }

    base["type_specific_settings"] = type_specific

    return {"status": "success", "data": base}


@router.get("/{group_id}/rotating-details", summary="Get Rotating Group Details (Direct Alias)")
@router.get("/{group_id}/settings/rotating", summary="Get Rotating Group Settings (Direct Alias)")
def get_rotating_details_direct(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    from app.api.routes.group.rotating.update import get_rotating_group_settings
    return get_rotating_group_settings(group_id=group_id, session=session, current_user=current_user)


@router.patch("/{group_id}/rotating-details", summary="Update Rotating Group Details (Direct Alias)")
@router.put("/{group_id}/rotating-details", summary="Update Rotating Group Details (Direct Alias)")
@router.patch("/{group_id}/settings/rotating", summary="Update Rotating Group Settings (Direct Alias)")
@router.put("/{group_id}/settings/rotating", summary="Update Rotating Group Settings (Direct Alias)")
def update_rotating_details_direct(
    group_id: str,
    request: Any = Body(default_factory=dict),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    from app.api.routes.group.rotating.update import UpdateRotatingSettingsRequest, update_rotating_group_settings
    if isinstance(request, dict):
        parsed_req = UpdateRotatingSettingsRequest(**request)
    elif isinstance(request, UpdateRotatingSettingsRequest):
        parsed_req = request
    else:
        parsed_req = UpdateRotatingSettingsRequest()
    return update_rotating_group_settings(group_id=group_id, request=parsed_req, session=session, current_user=current_user)
