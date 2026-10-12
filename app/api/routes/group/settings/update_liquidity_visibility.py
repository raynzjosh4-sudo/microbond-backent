from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupVisibilitySettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateLiquidityVisibilityRequest(BaseModel):
    vis_contribution_reminder_schedule: Optional[bool] = None
    vis_liquidity_buffer_coverage: Optional[bool] = None
    vis_late_fee_escalation: Optional[bool] = None
    vis_auto_debit_consent: Optional[bool] = None
    vis_emergency_contact: Optional[bool] = None
    vis_sms_call_reminders: Optional[bool] = None

@router.patch("/{group_id}/settings/liquidity-visibility", summary="Admin: Update Liquidity & Reminders Visibility")
def update_liquidity_visibility_settings(
    group_id: str, 
    request: UpdateLiquidityVisibilityRequest, 
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
        raise HTTPException(status_code=403, detail="Only the Group Admin can update visibility settings.")

    settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Visibility settings not found.")

    if request.vis_contribution_reminder_schedule is not None:
        settings.vis_contribution_reminder_schedule = request.vis_contribution_reminder_schedule
    if request.vis_liquidity_buffer_coverage is not None:
        settings.vis_liquidity_buffer_coverage = request.vis_liquidity_buffer_coverage
    if request.vis_late_fee_escalation is not None:
        settings.vis_late_fee_escalation = request.vis_late_fee_escalation
    if request.vis_auto_debit_consent is not None:
        settings.vis_auto_debit_consent = request.vis_auto_debit_consent
    if request.vis_emergency_contact is not None:
        settings.vis_emergency_contact = request.vis_emergency_contact
    if request.vis_sms_call_reminders is not None:
        settings.vis_sms_call_reminders = request.vis_sms_call_reminders

    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Liquidity & Reminders visibility settings updated successfully."}
