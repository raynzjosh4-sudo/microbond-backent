from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupCommunicationSettings, GroupVisibilitySettings
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])


class UpdateReportSettingsRequest(BaseModel):
    send_daily_group_summaries: Optional[bool] = None
    daily_summary_time: Optional[str] = None
    post_weekly_financial_reports: Optional[bool] = None
    weekly_report_day: Optional[str] = None
    weekly_report_time: Optional[str] = None
    send_deposit_due_prompts: Optional[bool] = None


def _format_time_to_12hr(time_str: Optional[str]) -> str:
    if not time_str:
        return "6:00 PM"
    try:
        parts = time_str.split(":")
        hr = int(parts[0])
        mn = int(parts[1]) if len(parts) > 1 else 0
        period = "AM" if hr < 12 else "PM"
        display_hr = 12 if hr in [0, 12] else hr % 12
        return f"{display_hr}:{mn:02d} {period}"
    except Exception:
        return time_str


@router.get("/{group_id}/settings/reports", summary="Get Reminders & Reports Settings")
def get_report_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the scheduled automated reminders, weekly financial reports,
    and daily group summary dispatch settings.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this group.")

    is_admin = (membership.role == "ADMIN")

    comm = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()
    if not comm:
        comm = GroupCommunicationSettings(group_id=group_id)
        session.add(comm)
        session.commit()
        session.refresh(comm)

    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()

    response_data = {
        "group_id": group_id,
        "is_admin": is_admin,
        "send_daily_group_summaries": comm.send_daily_group_summaries,
        "post_weekly_financial_reports": comm.post_weekly_financial_reports,
        "send_deposit_due_prompts": comm.send_deposit_due_prompts,
        "daily_summary_time": comm.daily_summary_time or "18:00",
        "daily_summary_time_display": _format_time_to_12hr(comm.daily_summary_time or "18:00"),
        "weekly_report_day": comm.weekly_report_day or "Sunday evening",
        "weekly_report_time": comm.weekly_report_time or "17:00"
    }

    if is_admin:
        response_data["visibility_status"] = {
            "vis_send_daily_group_summaries": vis.vis_send_daily_group_summaries if vis else True,
            "vis_post_weekly_financial_reports": vis.vis_post_weekly_financial_reports if vis else True,
            "vis_send_deposit_due_prompts": vis.vis_send_deposit_due_prompts if vis else True,
            "vis_daily_summary_time": vis.vis_daily_summary_time if vis else True,
            "vis_weekly_report_day": vis.vis_weekly_report_day if vis else True
        }
    else:
        if vis and not vis.vis_send_daily_group_summaries:
            response_data.pop("send_daily_group_summaries", None)
        if vis and not vis.vis_post_weekly_financial_reports:
            response_data.pop("post_weekly_financial_reports", None)
        if vis and not vis.vis_send_deposit_due_prompts:
            response_data.pop("send_deposit_due_prompts", None)
        if vis and not vis.vis_daily_summary_time:
            response_data.pop("daily_summary_time", None)
            response_data.pop("daily_summary_time_display", None)
        if vis and not vis.vis_weekly_report_day:
            response_data.pop("weekly_report_day", None)

    return {"status": "success", "data": response_data}


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
        settings = GroupCommunicationSettings(group_id=group_id)
        session.add(settings)

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

    AuditService.record_event(
        session=session,
        action="REPORTS_SETTINGS_UPDATED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={
            "updated_by": str(current_user.id),
            "send_daily_group_summaries": settings.send_daily_group_summaries,
            "daily_summary_time": settings.daily_summary_time,
            "post_weekly_financial_reports": settings.post_weekly_financial_reports,
            "weekly_report_day": settings.weekly_report_day,
            "send_deposit_due_prompts": settings.send_deposit_due_prompts
        },
        actor_user_id=current_user.id
    )

    session.commit()
    session.refresh(settings)

    return {
        "status": "success",
        "message": "Reminders & reports settings updated successfully.",
        "data": {
            "send_daily_group_summaries": settings.send_daily_group_summaries,
            "daily_summary_time": settings.daily_summary_time,
            "daily_summary_time_display": _format_time_to_12hr(settings.daily_summary_time),
            "post_weekly_financial_reports": settings.post_weekly_financial_reports,
            "weekly_report_day": settings.weekly_report_day,
            "send_deposit_due_prompts": settings.send_deposit_due_prompts
        }
    }
