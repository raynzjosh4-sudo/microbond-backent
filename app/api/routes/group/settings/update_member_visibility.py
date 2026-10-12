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


class UpdateMemberVisibilityScreenRequest(BaseModel):
    # Privacy & records
    vis_download_official_statement: Optional[bool] = None
    vis_chat_history_cleanup: Optional[bool] = None

    # Loan & investment messages (or transaction messages)
    vis_broadcast_individual_loan_receipts: Optional[bool] = None
    vis_announce_loan_disbursement_updates: Optional[bool] = None
    vis_show_transfer_receipts: Optional[bool] = None
    vis_announce_admin_transactions: Optional[bool] = None

    # Reminders & reports
    vis_send_daily_group_summaries: Optional[bool] = None
    vis_post_weekly_financial_reports: Optional[bool] = None
    vis_send_loan_due_prompts: Optional[bool] = None
    vis_daily_summary_time: Optional[bool] = None
    vis_weekly_report_day: Optional[bool] = None

    # Portfolio milestones & security
    vis_share_financial_snapshots: Optional[bool] = None
    vis_announce_system_events: Optional[bool] = None
    vis_post_security_rule_updates: Optional[bool] = None
    vis_post_loan_approval_polls: Optional[bool] = None
    vis_notify_important_rule_changes: Optional[bool] = None
    notify_important_rule_changes: Optional[bool] = None


@router.get("/{group_id}/settings/member-visibility", summary="Get Member Visibility Screen Structure & Toggles")
def get_member_visibility_screen(
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

    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()

    if not vis:
        raise HTTPException(status_code=404, detail="Visibility settings not found.")

    return {
        "status": "success",
        "data": {
            "privacy_and_records": {
                "vis_download_official_statement": vis.vis_download_official_statement,
                "vis_chat_history_cleanup": vis.vis_chat_history_cleanup
            },
            "loan_and_investment_messages": {
                "vis_broadcast_individual_loan_receipts": vis.vis_broadcast_individual_loan_receipts,
                "vis_announce_loan_disbursement_updates": vis.vis_announce_loan_disbursement_updates,
                "vis_show_transfer_receipts": vis.vis_show_transfer_receipts,
                "vis_announce_admin_transactions": vis.vis_announce_admin_transactions
            },
            "reminders_and_reports": {
                "vis_send_daily_group_summaries": vis.vis_send_daily_group_summaries,
                "vis_post_weekly_financial_reports": vis.vis_post_weekly_financial_reports,
                "vis_send_loan_due_prompts": vis.vis_send_loan_due_prompts,
                "vis_daily_summary_time": vis.vis_daily_summary_time,
                "vis_weekly_report_day": vis.vis_weekly_report_day
            },
            "portfolio_milestones_and_security": {
                "vis_share_financial_snapshots": vis.vis_share_financial_snapshots,
                "vis_announce_system_events": vis.vis_announce_system_events,
                "vis_post_security_rule_updates": vis.vis_post_security_rule_updates,
                "vis_post_loan_approval_polls": vis.vis_post_loan_approval_polls,
                "vis_notify_important_rule_changes": vis.vis_notify_important_rule_changes
            }
        }
    }


@router.patch("/{group_id}/settings/member-visibility", summary="Admin: Batch Update Member Visibility Screen Toggles")
def update_member_visibility_screen(
    group_id: str,
    request: UpdateMemberVisibilityScreenRequest,
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

    # Privacy & records
    if request.vis_download_official_statement is not None:
        settings.vis_download_official_statement = request.vis_download_official_statement
    if request.vis_chat_history_cleanup is not None:
        settings.vis_chat_history_cleanup = request.vis_chat_history_cleanup

    # Loan & investment messages
    if request.vis_broadcast_individual_loan_receipts is not None:
        settings.vis_broadcast_individual_loan_receipts = request.vis_broadcast_individual_loan_receipts
    if request.vis_announce_loan_disbursement_updates is not None:
        settings.vis_announce_loan_disbursement_updates = request.vis_announce_loan_disbursement_updates
    if request.vis_show_transfer_receipts is not None:
        settings.vis_show_transfer_receipts = request.vis_show_transfer_receipts
    if request.vis_announce_admin_transactions is not None:
        settings.vis_announce_admin_transactions = request.vis_announce_admin_transactions

    # Reminders & reports
    if request.vis_send_daily_group_summaries is not None:
        settings.vis_send_daily_group_summaries = request.vis_send_daily_group_summaries
    if request.vis_post_weekly_financial_reports is not None:
        settings.vis_post_weekly_financial_reports = request.vis_post_weekly_financial_reports
    if request.vis_send_loan_due_prompts is not None:
        settings.vis_send_loan_due_prompts = request.vis_send_loan_due_prompts
    if request.vis_daily_summary_time is not None:
        settings.vis_daily_summary_time = request.vis_daily_summary_time
    if request.vis_weekly_report_day is not None:
        settings.vis_weekly_report_day = request.vis_weekly_report_day

    # Portfolio milestones & security
    if request.vis_share_financial_snapshots is not None:
        settings.vis_share_financial_snapshots = request.vis_share_financial_snapshots
    if request.vis_announce_system_events is not None:
        settings.vis_announce_system_events = request.vis_announce_system_events
    if request.vis_post_security_rule_updates is not None:
        settings.vis_post_security_rule_updates = request.vis_post_security_rule_updates
    if request.vis_post_loan_approval_polls is not None:
        settings.vis_post_loan_approval_polls = request.vis_post_loan_approval_polls

    rule_val = request.vis_notify_important_rule_changes if request.vis_notify_important_rule_changes is not None else request.notify_important_rule_changes
    if rule_val is not None:
        settings.vis_notify_important_rule_changes = rule_val
        settings.notify_important_rule_changes = rule_val

    session.add(settings)
    session.commit()

    return {"status": "success", "message": "Member visibility settings updated successfully."}
