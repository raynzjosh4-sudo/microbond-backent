from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupCommunicationSettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateReportSettingsRequest(BaseModel):
    send_daily_group_summaries: Optional[bool] = None
    daily_summary_time: Optional[str] = None
    post_weekly_financial_reports: Optional[bool] = None
    weekly_report_day: Optional[str] = None
    weekly_report_time: Optional[str] = None
    send_deposit_due_prompts: Optional[bool] = None

@router.patch("/{group_id}/settings/reports", summary="Admin: Update Reminders & Reports Settings")
def update_report_settings(
    group_id: str, 
    request: UpdateReportSettingsRequest, 
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
        raise HTTPException(status_code=403, detail="Only the Group Admin can update report settings.")

    settings = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found.")

    if request.send_daily_group_summaries is not None:
        settings.send_daily_group_summaries = request.send_daily_group_summaries
    if request.daily_summary_time is not None:
        settings.daily_summary_time = request.daily_summary_time
    if request.post_weekly_financial_reports is not None:
        settings.post_weekly_financial_reports = request.post_weekly_financial_reports
    if request.weekly_report_day is not None:
        settings.weekly_report_day = request.weekly_report_day
    if request.weekly_report_time is not None:
        settings.weekly_report_time = request.weekly_report_time
    if request.send_deposit_due_prompts is not None:
        settings.send_deposit_due_prompts = request.send_deposit_due_prompts

    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Reminders & reports settings updated successfully."}
