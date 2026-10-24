from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupFinancialSettings, GroupVisibilitySettings
from app.models.group.investment_association import InvestmentClubOperationalSettings
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])


class UpdateLiquiditySettingsRequest(BaseModel):
    contribution_reminder_days_before: Optional[int] = None
    auto_debit_consent_required: Optional[bool] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    liquidity_buffer_percentage: Optional[float] = None
    liquidity_buffer_coverage_pct: Optional[int] = None
    enable_late_fee_escalation: Optional[bool] = None
    enable_sms_call_reminders: Optional[bool] = None


@router.get("/{group_id}/settings/liquidity", summary="Get Liquidity & Reminders Settings")
def get_liquidity_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this group.")

    is_admin = membership.role == "ADMIN"

    fin = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()

    if not fin or not vis:
        raise HTTPException(status_code=404, detail="Settings not found.")

    response = {
        "contribution_reminder_days_before": fin.contribution_reminder_days_before,
        "contribution_reminder_schedule_display": f"{fin.contribution_reminder_days_before} days before",
        "auto_debit_consent_required": fin.auto_debit_consent_required,
        "emergency_contact_name": fin.emergency_contact_name,
        "emergency_contact_phone": fin.emergency_contact_phone,
        "liquidity_buffer_percentage": fin.liquidity_buffer_percentage,
        "liquidity_buffer_coverage_display": f"{int(fin.liquidity_buffer_percentage)}%",
        "enable_late_fee_escalation": fin.enable_late_fee_escalation,
        "enable_sms_call_reminders": fin.enable_sms_call_reminders,
        "is_admin": is_admin
    }

    if is_admin:
        response["visibility_status"] = {
            "vis_contribution_reminder_schedule": vis.vis_contribution_reminder_schedule,
            "vis_auto_debit_consent": vis.vis_auto_debit_consent,
            "vis_emergency_contact": vis.vis_emergency_contact,
            "vis_liquidity_buffer_coverage": vis.vis_liquidity_buffer_coverage,
            "vis_late_fee_escalation": vis.vis_late_fee_escalation,
            "vis_sms_call_reminders": vis.vis_sms_call_reminders
        }
    else:
        # Strip hidden fields if user is regular member and admin has hidden them
        if not vis.vis_contribution_reminder_schedule:
            response.pop("contribution_reminder_days_before", None)
            response.pop("contribution_reminder_schedule_display", None)
        if not vis.vis_auto_debit_consent:
            response.pop("auto_debit_consent_required", None)
        if not vis.vis_emergency_contact:
            response.pop("emergency_contact_name", None)
            response.pop("emergency_contact_phone", None)
        if not vis.vis_liquidity_buffer_coverage:
            response.pop("liquidity_buffer_percentage", None)
            response.pop("liquidity_buffer_coverage_display", None)
        if not vis.vis_late_fee_escalation:
            response.pop("enable_late_fee_escalation", None)
        if not vis.vis_sms_call_reminders:
            response.pop("enable_sms_call_reminders", None)

    return {"status": "success", "data": response}


@router.patch("/{group_id}/settings/liquidity", summary="Admin: Update Liquidity & Reminders Settings")
def update_liquidity_settings(
    group_id: str,
    request: UpdateLiquiditySettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()

    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update liquidity settings.")

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    settings = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()

    if not settings:
        raise HTTPException(status_code=404, detail="Financial settings not found.")

    if request.contribution_reminder_days_before is not None:
        if request.contribution_reminder_days_before < 0:
            raise HTTPException(status_code=400, detail="Reminder days cannot be negative.")
        settings.contribution_reminder_days_before = request.contribution_reminder_days_before

    if request.auto_debit_consent_required is not None:
        settings.auto_debit_consent_required = request.auto_debit_consent_required

    if request.emergency_contact_name is not None:
        settings.emergency_contact_name = request.emergency_contact_name

    if request.emergency_contact_phone is not None:
        settings.emergency_contact_phone = request.emergency_contact_phone

    # Liquidity buffer percentage
    buffer_val = request.liquidity_buffer_percentage
    if buffer_val is None and request.liquidity_buffer_coverage_pct is not None:
        buffer_val = float(request.liquidity_buffer_coverage_pct)

    if buffer_val is not None:
        if buffer_val < 0 or buffer_val > 100:
            raise HTTPException(status_code=400, detail="Liquidity buffer must be between 0% and 100%.")
        settings.liquidity_buffer_percentage = buffer_val

    if request.enable_late_fee_escalation is not None:
        settings.enable_late_fee_escalation = request.enable_late_fee_escalation

    if request.enable_sms_call_reminders is not None:
        settings.enable_sms_call_reminders = request.enable_sms_call_reminders

    session.add(settings)

    # Sync into InvestmentClubOperationalSettings if this is an investment club
    if group.type == "INVESTMENT_CLUB":
        club_ops = session.exec(
            select(InvestmentClubOperationalSettings).where(
                InvestmentClubOperationalSettings.group_id == group_id
            )
        ).first()
        if club_ops:
            if request.contribution_reminder_days_before is not None:
                club_ops.contribution_reminder_days_before = request.contribution_reminder_days_before
            if request.auto_debit_consent_required is not None:
                club_ops.auto_debit_consent_required = request.auto_debit_consent_required
            if request.emergency_contact_name is not None:
                club_ops.emergency_contact_name = request.emergency_contact_name
            if request.emergency_contact_phone is not None:
                club_ops.emergency_contact_phone = request.emergency_contact_phone
            if buffer_val is not None:
                club_ops.liquidity_buffer_coverage_pct = int(buffer_val)
            if request.enable_late_fee_escalation is not None:
                club_ops.enable_late_fee_escalation = request.enable_late_fee_escalation
            if request.enable_sms_call_reminders is not None:
                club_ops.enable_sms_call_reminders = request.enable_sms_call_reminders
            session.add(club_ops)

    AuditService.record_event(
        session=session,
        action="LIQUIDITY_SETTINGS_UPDATED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={
            "updated_by": str(current_user.id),
            "contribution_reminder_days_before": settings.contribution_reminder_days_before,
            "auto_debit_consent_required": settings.auto_debit_consent_required,
            "emergency_contact_name": settings.emergency_contact_name,
            "emergency_contact_phone": settings.emergency_contact_phone,
            "liquidity_buffer_percentage": settings.liquidity_buffer_percentage,
            "enable_late_fee_escalation": settings.enable_late_fee_escalation,
            "enable_sms_call_reminders": settings.enable_sms_call_reminders,
        },
        actor_user_id=current_user.id
    )

    session.commit()

    return {
        "status": "success",
        "message": "Liquidity & Reminders settings updated successfully.",
        "data": {
            "contribution_reminder_days_before": settings.contribution_reminder_days_before,
            "auto_debit_consent_required": settings.auto_debit_consent_required,
            "emergency_contact_name": settings.emergency_contact_name,
            "emergency_contact_phone": settings.emergency_contact_phone,
            "liquidity_buffer_percentage": settings.liquidity_buffer_percentage,
            "enable_late_fee_escalation": settings.enable_late_fee_escalation,
            "enable_sms_call_reminders": settings.enable_sms_call_reminders
        }
    }
