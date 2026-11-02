from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.dependencies import get_current_user
from app.api.routes.group.settings.common_settings_messages import (
    broadcast_common_setting_changes,
)
from app.core.database import get_session
from app.models.group.group import Group, GroupMembership
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.settings import (
    GroupCommonSettings,
    GroupFinancialSettings,
    GroupGovernanceSettings,
)
from app.models.group.target_savings import TargetSavingsGroupDetails
from app.models.group.shared_wallet import SharedWalletConfig
from app.models.group.welfare_fund import WelfareFundOperationalSettings
from app.models.user.user import User
from app.utils.time.now_epoch_ms import now_epoch_ms

router = APIRouter(prefix="/api/v1/groups", tags=["Group Common Settings"])

LatePaymentPolicy = Literal[
    "STRIKE_AND_KEEP",
    "KICK_AND_BAN",
    "USE_GUARANTOR_FUNDS",
    "RECORD_STRIKE",
    "REMOVE_AND_REFUND",
    "SUSPEND_CLAIM_RIGHTS",
]
LATE_PAYMENT_POLICIES = {
    "STRIKE_AND_KEEP",
    "KICK_AND_BAN",
    "USE_GUARANTOR_FUNDS",
    "RECORD_STRIKE",
    "REMOVE_AND_REFUND",
    "SUSPEND_CLAIM_RIGHTS",
}


class CommonSettingsUpdateRequest(BaseModel):
    allow_partial_payments: Optional[bool] = None
    minimum_partial_payment_amount: Optional[float] = Field(default=None, gt=0)
    minimum_kyc_tier: Optional[int] = Field(default=None, ge=0, le=3)
    group_start_time: Optional[int] = Field(default=None, ge=0)
    require_guarantor: Optional[bool] = None
    maximum_member_capacity: Optional[int] = Field(default=None, ge=1)
    collection_frequency_days: Optional[int] = Field(default=None, ge=0)
    grace_period_hours: Optional[int] = Field(default=None, ge=0)
    late_payment_policy: Optional[LatePaymentPolicy] = None
    payment_approval_threshold: Optional[int] = Field(default=None, ge=0)
    allow_advance_payments: Optional[bool] = None


def _first(session: Session, model, group_id: str):
    return session.exec(
        select(model).where(model.group_id == group_id)
    ).first()


def _get_or_initialize_settings(
    session: Session,
    group: Group,
) -> GroupCommonSettings:
    settings = _first(session, GroupCommonSettings, group.group_id)
    if settings:
        return settings

    rotating = _first(session, RotatingGroupDetails, group.group_id)
    governance = _first(session, GroupGovernanceSettings, group.group_id)
    financial = _first(session, GroupFinancialSettings, group.group_id)
    target_savings = _first(session, TargetSavingsGroupDetails, group.group_id)
    shared_wallet = _first(session, SharedWalletConfig, group.group_id)
    welfare = _first(session, WelfareFundOperationalSettings, group.group_id)

    late_payment_policy = (
        target_savings.missed_payment_action
        if target_savings
        else welfare.missed_payment_action
        if welfare
        else financial.arrears_policy
        if financial
        else "STRIKE_AND_KEEP"
    )
    if late_payment_policy not in LATE_PAYMENT_POLICIES:
        late_payment_policy = "STRIKE_AND_KEEP"

    settings = GroupCommonSettings(
        group_id=group.group_id,
        allow_partial_payments=rotating.allow_partial_payments if rotating else False,
        minimum_partial_payment_amount=(
            rotating.minimum_partial_payment_amount if rotating else None
        ),
        minimum_kyc_tier=(
            rotating.minimum_kyc_tier
            if rotating
            else target_savings.minimum_kyc_tier
            if target_savings
            else shared_wallet.minimum_kyc_tier
            if shared_wallet
            else governance.minimum_kyc_tier
            if governance
            else 1
        ),
        group_start_time=rotating.group_start_time if rotating else group.start_date,
        require_guarantor=(
            rotating.require_guarantor
            if rotating
            else governance.require_guarantors
            if governance
            else False
        ),
        maximum_member_capacity=group.max_members,
        collection_frequency_days=(
            rotating.collection_frequency_days
            if rotating
            else target_savings.collection_frequency_days
            if target_savings
            else shared_wallet.collection_frequency_days
            if shared_wallet
            else None
        ),
        grace_period_hours=(
            financial.grace_period_hours
            if financial
            else target_savings.grace_period_hours
            if target_savings
            else 24
        ),
        late_payment_policy=late_payment_policy,
        allow_advance_payments=(
            rotating.allow_advance_deposits if rotating else True
        ),
    )
    return settings


def _sync_legacy_settings(
    session: Session,
    group: Group,
    settings: GroupCommonSettings,
    changed_fields: set[str],
) -> None:
    rotating = _first(session, RotatingGroupDetails, group.group_id)
    if rotating:
        field_map = {
            "allow_partial_payments": "allow_partial_payments",
            "minimum_partial_payment_amount": "minimum_partial_payment_amount",
            "minimum_kyc_tier": "minimum_kyc_tier",
            "group_start_time": "group_start_time",
            "require_guarantor": "require_guarantor",
            "collection_frequency_days": "collection_frequency_days",
            "allow_advance_payments": "allow_advance_deposits",
        }
        for setting_field, model_field in field_map.items():
            if setting_field in changed_fields:
                setattr(rotating, model_field, getattr(settings, setting_field))
        session.add(rotating)

    if "maximum_member_capacity" in changed_fields:
        group.max_members = settings.maximum_member_capacity
        session.add(group)

    if "minimum_kyc_tier" in changed_fields or "require_guarantor" in changed_fields:
        governance = _first(session, GroupGovernanceSettings, group.group_id)
        if governance:
            if "minimum_kyc_tier" in changed_fields:
                governance.minimum_kyc_tier = settings.minimum_kyc_tier
            if "require_guarantor" in changed_fields:
                governance.require_guarantors = settings.require_guarantor
            session.add(governance)

    if "collection_frequency_days" in changed_fields or "minimum_kyc_tier" in changed_fields:
        target_savings = _first(session, TargetSavingsGroupDetails, group.group_id)
        if target_savings:
            if "collection_frequency_days" in changed_fields:
                target_savings.collection_frequency_days = settings.collection_frequency_days
            if "minimum_kyc_tier" in changed_fields:
                target_savings.minimum_kyc_tier = settings.minimum_kyc_tier
            session.add(target_savings)
        shared_wallet = _first(session, SharedWalletConfig, group.group_id)
        if shared_wallet:
            if "collection_frequency_days" in changed_fields:
                shared_wallet.collection_frequency_days = settings.collection_frequency_days
            if "minimum_kyc_tier" in changed_fields:
                shared_wallet.minimum_kyc_tier = settings.minimum_kyc_tier
            session.add(shared_wallet)

    if "grace_period_hours" in changed_fields or "late_payment_policy" in changed_fields:
        financial = _first(session, GroupFinancialSettings, group.group_id)
        if financial:
            if "grace_period_hours" in changed_fields:
                financial.grace_period_hours = settings.grace_period_hours
            if "late_payment_policy" in changed_fields:
                financial.arrears_policy = settings.late_payment_policy
            session.add(financial)
        target_savings = _first(session, TargetSavingsGroupDetails, group.group_id)
        if target_savings:
            if "grace_period_hours" in changed_fields:
                target_savings.grace_period_hours = settings.grace_period_hours
            if "late_payment_policy" in changed_fields:
                target_savings.missed_payment_action = settings.late_payment_policy
            session.add(target_savings)
        welfare = _first(session, WelfareFundOperationalSettings, group.group_id)
        if welfare and "late_payment_policy" in changed_fields:
            welfare.missed_payment_action = settings.late_payment_policy
            session.add(welfare)


@router.get("/{group_id}/settings/common", summary="Get Common Group Settings")
def get_common_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    group = _first(session, Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE",
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member to view settings.")

    settings = _get_or_initialize_settings(session, group)
    return {
        "status": "success",
        "data": settings.model_dump(
            exclude={"id", "group_id", "updated_at"}
        ),
    }


@router.patch("/{group_id}/settings/common", summary="Update Common Group Settings")
def update_common_settings(
    group_id: str,
    request: CommonSettingsUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    group = _first(session, Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE",
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Only an active Group Admin can update settings.")

    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="At least one setting must be provided.")

    if "maximum_member_capacity" in updates:
        capacity = updates["maximum_member_capacity"]
        if capacity is not None:
            active_members = session.exec(
                select(GroupMembership).where(
                    GroupMembership.group_id == group_id,
                    GroupMembership.status == "ACTIVE",
                )
            ).all()
            if capacity < len(active_members):
                raise HTTPException(
                    status_code=400,
                    detail="Cannot lower capacity below the current number of active members.",
                )

    if "late_payment_policy" in updates:
        allowed_policies_by_type = {
            "GOAL_SAVINGS": {"RECORD_STRIKE", "REMOVE_AND_REFUND"},
            "WELFARE_FUND": {"SUSPEND_CLAIM_RIGHTS", "RECORD_STRIKE"},
            "MERRY_GO_ROUND": {
                "STRIKE_AND_KEEP",
                "KICK_AND_BAN",
                "USE_GUARANTOR_FUNDS",
            },
        }
        allowed_policies = allowed_policies_by_type.get(group.type)
        if allowed_policies and updates["late_payment_policy"] not in allowed_policies:
            raise HTTPException(
                status_code=422,
                detail=f"Late payment policy is not supported for {group.type}.",
            )

    settings = _get_or_initialize_settings(session, group)
    effective_allow_partial_payments = updates.get(
        "allow_partial_payments", settings.allow_partial_payments
    )
    effective_minimum_amount = updates.get(
        "minimum_partial_payment_amount",
        settings.minimum_partial_payment_amount,
    )
    if effective_allow_partial_payments and effective_minimum_amount is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "minimum_partial_payment_amount is required when "
                "allow_partial_payments is enabled."
            ),
        )

    changed_values = {
        field: (getattr(settings, field), value)
        for field, value in updates.items()
        if getattr(settings, field) != value
    }

    for field, value in updates.items():
        if value is None and field not in {
            "maximum_member_capacity",
            "payment_approval_threshold",
            "minimum_partial_payment_amount",
        }:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null.")
        setattr(settings, field, value)
    settings.updated_at = now_epoch_ms()
    session.add(settings)
    _sync_legacy_settings(session, group, settings, set(updates))
    session.commit()
    session.refresh(settings)
    response_data = settings.model_dump(
        exclude={"id", "group_id", "updated_at"}
    )

    if changed_values:
        broadcast_common_setting_changes(
            group_id=group_id,
            changed_values=changed_values,
            settings=settings,
            admin=current_user,
            session=session,
        )

    return {
        "status": "success",
        "message": "Common settings updated.",
        "data": response_data,
    }
