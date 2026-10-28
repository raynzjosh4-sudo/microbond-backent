from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupVisibilitySettings
from app.models.group.long_term import TargetSavingsGroupDetails
from app.services.audit_service import AuditService
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])


class UpdateMemberVisibilityScreenRequest(BaseModel):
    # 1. Goal controls
    lock_funds: Optional[bool] = Field(default=None, description="Lock/freeze contributions until goal is reached")
    is_locked: Optional[bool] = Field(default=None, description="Alias for lock_funds")
    hide_leaderboard: Optional[bool] = Field(default=None, description="Hide member rankings / contributions leaderboard")
    vis_lock_funds: Optional[bool] = Field(default=None, description="Alias for lock_funds")
    vis_hide_leaderboard: Optional[bool] = Field(default=None, description="Alias for hide_leaderboard")

    # 2. Governance & audit
    vis_multi_signature_roster: Optional[bool] = Field(default=None, description="Show/hide multi-signature roster")
    vis_active_audit_status: Optional[bool] = Field(default=None, description="Show/hide active audit status")
    vis_approval_quorum: Optional[bool] = Field(default=None, description="Show/hide approval quorum")
    vis_pending_payout_queue: Optional[bool] = Field(default=None, description="Show/hide pending payout/disbursals queue")
    vis_pending_disbursals: Optional[bool] = Field(default=None, description="Alias for vis_pending_payout_queue")
    vis_require_multi_signature: Optional[bool] = Field(default=None, description="Show/hide require multi-sig switch")
    vis_time_lock_disbursals: Optional[bool] = Field(default=None, description="Show/hide time-lock disbursals switch")

    # 3. Trust & members
    vis_guarantor_required: Optional[bool] = Field(default=None, description="Show/hide guarantor required setting")

    # 4. Liquidity & reminders
    vis_contribution_reminder_schedule: Optional[bool] = Field(default=None, description="Show/hide reminder schedule")
    vis_liquidity_buffer_coverage: Optional[bool] = Field(default=None, description="Show/hide liquidity buffer coverage")
    vis_late_fee_escalation: Optional[bool] = Field(default=None, description="Show/hide late fee escalation")

    # 5. Privacy & records
    vis_download_official_statement: Optional[bool] = Field(default=None, description="Show/hide official statement download")
    vis_chat_history_cleanup: Optional[bool] = Field(default=None, description="Show/hide chat history cleanup")
    vis_member_total_savings: Optional[bool] = Field(default=None, description="Show/hide member total saved balance")

    # 6. Contribution / Transaction messages
    vis_broadcast_individual_deposit_receipts: Optional[bool] = Field(default=None, description="Broadcast individual contribution receipts in chat")
    vis_announce_payout_updates: Optional[bool] = Field(default=None, description="Announce approved withdrawal updates in chat")
    vis_show_transfer_receipts: Optional[bool] = Field(default=None, description="Show transfer receipts in chat")
    vis_announce_admin_transactions: Optional[bool] = Field(default=None, description="Announce admin transactions in chat")

    # 7. Reminders & reports
    vis_send_daily_group_summaries: Optional[bool] = Field(default=None, description="Show/hide daily group summaries")
    vis_post_weekly_financial_reports: Optional[bool] = Field(default=None, description="Show/hide weekly financial reports")
    vis_send_deposit_due_prompts: Optional[bool] = Field(default=None, description="Show/hide contribution due prompts")
    vis_daily_summary_time: Optional[bool] = Field(default=None, description="Show/hide daily summary time")
    vis_weekly_report_day: Optional[bool] = Field(default=None, description="Show/hide weekly report day")

    # 8. Goal milestones & security
    vis_share_financial_snapshots: Optional[bool] = Field(default=None, description="Show/hide financial snapshots")
    vis_announce_system_events: Optional[bool] = Field(default=None, description="Show/hide system events")
    vis_post_security_rule_updates: Optional[bool] = Field(default=None, description="Show/hide security rule updates")
    vis_post_group_approval_polls: Optional[bool] = Field(default=None, description="Show/hide group approval polls")
    vis_notify_important_rule_changes: Optional[bool] = Field(default=None, description="Show/hide notify important rule changes")
    notify_important_rule_changes: Optional[bool] = Field(default=None, description="Alias for vis_notify_important_rule_changes")

    # Deposit widget visibility
    deposit_widget_visibility: Optional[str] = Field(default=None, description="ALL_MEMBERS, ADMIN_ONLY, ADMIN_AND_TREASURER")


@router.get("/{group_id}/settings/member-visibility", summary="Get Member Visibility Master Screen Toggles")
def get_member_visibility_screen(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the complete Member Visibility master screen configuration,
    organized across all 8 functional group settings sections.
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

    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    if not vis:
        vis = GroupVisibilitySettings(group_id=group_id)
        session.add(vis)
        session.commit()
        session.refresh(vis)

    details = session.exec(
        select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
    ).first()
    lock_funds_val = details.lock_funds if details else False
    hide_leaderboard_val = details.hide_leaderboard if details else False

    # Structured response matching the 8 sections in the UI
    sections = {
        "goal_controls": {
            "lock_funds": lock_funds_val,
            "hide_leaderboard": hide_leaderboard_val,
        },
        "governance_and_audit": {
            "multi_signature_signer_roster": vis.vis_multi_signature_roster,
            "active_audit_status": vis.vis_active_audit_status,
            "approval_quorum": vis.vis_approval_quorum,
            "pending_disbursals": vis.vis_pending_payout_queue,
            "require_multi_signature": vis.vis_require_multi_signature,
            "time_lock_disbursals": vis.vis_time_lock_disbursals,
        },
        "trust_and_members": {
            "guarantor_required": vis.vis_guarantor_required,
        },
        "liquidity_and_reminders": {
            "contribution_reminder_schedule": vis.vis_contribution_reminder_schedule,
            "liquidity_buffer_coverage": vis.vis_liquidity_buffer_coverage,
            "late_fee_escalation": vis.vis_late_fee_escalation,
        },
        "privacy_and_records": {
            "download_official_statement": vis.vis_download_official_statement,
            "chat_history_cleanup": vis.vis_chat_history_cleanup,
        },
        "contribution_messages": {
            "broadcast_individual_contribution_receipts": vis.vis_broadcast_individual_deposit_receipts,
            "announce_approved_withdrawal_updates": vis.vis_announce_payout_updates,
            "show_transfer_receipts": vis.vis_show_transfer_receipts,
            "announce_admin_transactions": vis.vis_announce_admin_transactions,
        },
        "reminders_and_reports": {
            "send_daily_group_summaries": vis.vis_send_daily_group_summaries,
            "post_weekly_financial_reports": vis.vis_post_weekly_financial_reports,
            "send_contribution_due_prompts": vis.vis_send_deposit_due_prompts,
            "daily_summary_time": vis.vis_daily_summary_time,
            "weekly_report_day": vis.vis_weekly_report_day,
        },
        "goal_milestones_and_security": {
            "share_financial_snapshots": vis.vis_share_financial_snapshots,
            "announce_system_events": vis.vis_announce_system_events,
            "post_security_rule_updates": vis.vis_post_security_rule_updates,
            "post_group_approval_polls": vis.vis_post_group_approval_polls,
            "notify_members_about_important_rule_changes": vis.vis_notify_important_rule_changes,
        }
    }

    # Flat toggle dictionary for direct key-value binding in Android
    flat_toggles = {
        # Goal controls
        "lock_funds": lock_funds_val,
        "hide_leaderboard": hide_leaderboard_val,
        # Governance & audit
        "vis_multi_signature_roster": vis.vis_multi_signature_roster,
        "vis_active_audit_status": vis.vis_active_audit_status,
        "vis_approval_quorum": vis.vis_approval_quorum,
        "vis_pending_payout_queue": vis.vis_pending_payout_queue,
        "vis_pending_disbursals": vis.vis_pending_payout_queue,
        "vis_require_multi_signature": vis.vis_require_multi_signature,
        "vis_time_lock_disbursals": vis.vis_time_lock_disbursals,
        # Trust & members
        "vis_guarantor_required": vis.vis_guarantor_required,
        # Liquidity & reminders
        "vis_contribution_reminder_schedule": vis.vis_contribution_reminder_schedule,
        "vis_liquidity_buffer_coverage": vis.vis_liquidity_buffer_coverage,
        "vis_late_fee_escalation": vis.vis_late_fee_escalation,
        # Privacy & records
        "vis_download_official_statement": vis.vis_download_official_statement,
        "vis_chat_history_cleanup": vis.vis_chat_history_cleanup,
        # Contribution messages
        "vis_broadcast_individual_deposit_receipts": vis.vis_broadcast_individual_deposit_receipts,
        "vis_announce_payout_updates": vis.vis_announce_payout_updates,
        "vis_show_transfer_receipts": vis.vis_show_transfer_receipts,
        "vis_announce_admin_transactions": vis.vis_announce_admin_transactions,
        # Reminders & reports
        "vis_send_daily_group_summaries": vis.vis_send_daily_group_summaries,
        "vis_post_weekly_financial_reports": vis.vis_post_weekly_financial_reports,
        "vis_send_deposit_due_prompts": vis.vis_send_deposit_due_prompts,
        "vis_daily_summary_time": vis.vis_daily_summary_time,
        "vis_weekly_report_day": vis.vis_weekly_report_day,
        # Goal milestones & security
        "vis_share_financial_snapshots": vis.vis_share_financial_snapshots,
        "vis_announce_system_events": vis.vis_announce_system_events,
        "vis_post_security_rule_updates": vis.vis_post_security_rule_updates,
        "vis_post_group_approval_polls": vis.vis_post_group_approval_polls,
        "vis_notify_important_rule_changes": vis.vis_notify_important_rule_changes,
    }

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "is_admin": is_admin,
            "sections": sections,
            "toggles": flat_toggles
        }
    }


@router.patch("/{group_id}/settings/member-visibility", summary="Admin: Batch Update Member Visibility Screen Toggles")
def update_member_visibility_screen(
    group_id: str,
    request: UpdateMemberVisibilityScreenRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates any member visibility toggle across all 8 settings categories.
    Only group administrators can modify these visibility rules.
    """
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
        settings = GroupVisibilitySettings(group_id=group_id)
        session.add(settings)

    # 1. Goal controls
    details = session.exec(
        select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
    ).first()
    
    lock_val = request.lock_funds if request.lock_funds is not None else (
        request.is_locked if request.is_locked is not None else request.vis_lock_funds
    )
    hide_lb_val = request.hide_leaderboard if request.hide_leaderboard is not None else request.vis_hide_leaderboard

    if details:
        if lock_val is not None:
            details.lock_funds = lock_val
        if hide_lb_val is not None:
            details.hide_leaderboard = hide_lb_val
        session.add(details)

    # 2. Governance & audit
    if request.vis_multi_signature_roster is not None:
        settings.vis_multi_signature_roster = request.vis_multi_signature_roster
    if request.vis_active_audit_status is not None:
        settings.vis_active_audit_status = request.vis_active_audit_status
    if request.vis_approval_quorum is not None:
        settings.vis_approval_quorum = request.vis_approval_quorum
    
    pending_payout_val = request.vis_pending_payout_queue if request.vis_pending_payout_queue is not None else request.vis_pending_disbursals
    if pending_payout_val is not None:
        settings.vis_pending_payout_queue = pending_payout_val

    if request.vis_require_multi_signature is not None:
        settings.vis_require_multi_signature = request.vis_require_multi_signature
    if request.vis_time_lock_disbursals is not None:
        settings.vis_time_lock_disbursals = request.vis_time_lock_disbursals

    # 3. Trust & members
    if request.vis_guarantor_required is not None:
        settings.vis_guarantor_required = request.vis_guarantor_required

    # 4. Liquidity & reminders
    if request.vis_contribution_reminder_schedule is not None:
        settings.vis_contribution_reminder_schedule = request.vis_contribution_reminder_schedule
    if request.vis_liquidity_buffer_coverage is not None:
        settings.vis_liquidity_buffer_coverage = request.vis_liquidity_buffer_coverage
    if request.vis_late_fee_escalation is not None:
        settings.vis_late_fee_escalation = request.vis_late_fee_escalation

    # 5. Privacy & records
    if request.vis_download_official_statement is not None:
        settings.vis_download_official_statement = request.vis_download_official_statement
    if request.vis_chat_history_cleanup is not None:
        settings.vis_chat_history_cleanup = request.vis_chat_history_cleanup
    if request.vis_member_total_savings is not None:
        settings.vis_member_total_savings = request.vis_member_total_savings

    # 6. Contribution messages
    if request.vis_broadcast_individual_deposit_receipts is not None:
        settings.vis_broadcast_individual_deposit_receipts = request.vis_broadcast_individual_deposit_receipts
    if request.vis_announce_payout_updates is not None:
        settings.vis_announce_payout_updates = request.vis_announce_payout_updates
    if request.vis_show_transfer_receipts is not None:
        settings.vis_show_transfer_receipts = request.vis_show_transfer_receipts
    if request.vis_announce_admin_transactions is not None:
        settings.vis_announce_admin_transactions = request.vis_announce_admin_transactions

    # 7. Reminders & reports
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

    # 8. Goal milestones & security
    if request.vis_share_financial_snapshots is not None:
        settings.vis_share_financial_snapshots = request.vis_share_financial_snapshots
    if request.vis_announce_system_events is not None:
        settings.vis_announce_system_events = request.vis_announce_system_events
    if request.vis_post_security_rule_updates is not None:
        settings.vis_post_security_rule_updates = request.vis_post_security_rule_updates
    if request.vis_post_group_approval_polls is not None:
        settings.vis_post_group_approval_polls = request.vis_post_group_approval_polls
    
    notify_val = request.vis_notify_important_rule_changes if request.vis_notify_important_rule_changes is not None else request.notify_important_rule_changes
    if notify_val is not None:
        settings.vis_notify_important_rule_changes = notify_val

    session.add(settings)

    AuditService.record_event(
        session=session,
        action="MEMBER_VISIBILITY_SETTINGS_UPDATED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={
            "updated_by": str(current_user.id),
            "updated_fields": {k: v for k, v in request.dict().items() if v is not None}
        },
        actor_user_id=current_user.id
    )

    session.commit()
    session.refresh(settings)

    admin_name = current_user.full_name or "Admin"
    system_msg = broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"👁️ Group Visibility Settings updated by {admin_name}. Information and report transparency rules have been refreshed for this group.",
        message_type="SYSTEM_EVENT",
        sender_id="SYSTEM",
        session=session,
        background_tasks=background_tasks,
        attachments=[{
            "category": "SETTINGS_UPDATE",
            "setting_type": "VISIBILITY",
            "admin_id": str(current_user.id),
            "admin_name": admin_name
        }]
    )
    if background_tasks is None and system_msg:
        try:
            import asyncio
            asyncio.create_task(
                ws_manager.broadcast_to_group(
                    group_id,
                    {
                        "event_type": "NEW_MESSAGE",
                        "message": system_msg.model_dump(mode="json")
                    }
                )
            )
        except Exception:
            pass

    return {
        "status": "success",
        "message": "Member visibility settings updated successfully.",
        "data": {
            "group_id": group_id,
            "vis_multi_signature_roster": settings.vis_multi_signature_roster,
            "vis_active_audit_status": settings.vis_active_audit_status,
            "vis_approval_quorum": settings.vis_approval_quorum,
            "vis_pending_payout_queue": settings.vis_pending_payout_queue,
            "vis_require_multi_signature": settings.vis_require_multi_signature,
            "vis_time_lock_disbursals": settings.vis_time_lock_disbursals,
            "vis_guarantor_required": settings.vis_guarantor_required,
            "vis_contribution_reminder_schedule": settings.vis_contribution_reminder_schedule,
            "vis_liquidity_buffer_coverage": settings.vis_liquidity_buffer_coverage,
            "vis_late_fee_escalation": settings.vis_late_fee_escalation,
            "vis_download_official_statement": settings.vis_download_official_statement,
            "vis_chat_history_cleanup": settings.vis_chat_history_cleanup,
            "vis_broadcast_individual_deposit_receipts": settings.vis_broadcast_individual_deposit_receipts,
            "vis_announce_payout_updates": settings.vis_announce_payout_updates,
            "vis_show_transfer_receipts": settings.vis_show_transfer_receipts,
            "vis_announce_admin_transactions": settings.vis_announce_admin_transactions,
            "vis_send_daily_group_summaries": settings.vis_send_daily_group_summaries,
            "vis_post_weekly_financial_reports": settings.vis_post_weekly_financial_reports,
            "vis_send_deposit_due_prompts": settings.vis_send_deposit_due_prompts,
            "vis_daily_summary_time": settings.vis_daily_summary_time,
            "vis_weekly_report_day": settings.vis_weekly_report_day,
            "vis_share_financial_snapshots": settings.vis_share_financial_snapshots,
            "vis_announce_system_events": settings.vis_announce_system_events,
            "vis_post_security_rule_updates": settings.vis_post_security_rule_updates,
            "vis_post_group_approval_polls": settings.vis_post_group_approval_polls,
            "vis_notify_important_rule_changes": settings.vis_notify_important_rule_changes
        }
    }
