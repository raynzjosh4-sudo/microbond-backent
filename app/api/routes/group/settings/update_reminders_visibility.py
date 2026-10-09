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

class UpdateRemindersVisibilityRequest(BaseModel):
    vis_send_daily_group_summaries: Optional[bool] = None
    vis_post_weekly_financial_reports: Optional[bool] = None
    vis_send_deposit_due_prompts: Optional[bool] = None
    vis_daily_summary_time: Optional[bool] = None
    vis_weekly_report_day: Optional[bool] = None

@router.patch("/{group_id}/settings/reminders-visibility", summary="Admin: Update Reminders & Reports Visibility")
def update_reminders_visibility_settings(
    group_id: str, 
    request: UpdateRemindersVisibilityRequest, 
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

    if request.vis_send_daily_group_summaries is not None:
        settings.vis_send_daily_group_summaries = request.vis_send_daily_group_summaries
    if request.vis_post_weekly_financial_reports is not None:
        settings.vis_post_weekly_financial_reports = request.vis_post_weekly_financial_reports
    if request.vis_send_deposit_due_prompts is not None:
        settings.vis_send_deposit_due_prompts = request.vis_send_deposit_due_prompts
    if request.vis_daily_summary_time is not None:
        settings.vis_daily_summary_time = request.vis_daily_summary_time
    if request.vis_weekly_report_day is not None:
        settings.vis_weekly_report_day = request.vis_weekly_report_day

    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Reminders & reports visibility updated successfully."}
