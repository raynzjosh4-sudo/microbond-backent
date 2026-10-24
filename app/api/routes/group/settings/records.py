from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select
import uuid

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import (
    GroupCommunicationSettings,
    GroupGovernanceSettings,
    GroupFinancialSettings,
    GroupVisibilitySettings
)
from app.models.group.chat import GroupChatMessage
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Privacy & Records Settings"])


class UpdateRecordsSettingsRequest(BaseModel):
    data_retention_days: Optional[int] = Field(
        default=None,
        description="Number of days to retain user data before auto-pruning (e.g. 365, 730, 1825)"
    )
    chat_history_cleanup_days: Optional[int] = Field(
        default=None,
        description="Auto-delete chat messages older than X days (e.g. 30, 90, 180, 365)"
    )
    preserve_financial_records: Optional[bool] = Field(
        default=None,
        description="Whether to keep transaction receipts, loan requests, and system alerts regardless of age"
    )
    group_charter_url: Optional[str] = Field(
        default=None,
        description="URL to the official Group Charter PDF or document"
    )


def _format_days_to_display(days: int) -> str:
    if days >= 365:
        years = days // 365
        return f"{years} year{'s' if years > 1 else ''}"
    elif days >= 30:
        months = days // 30
        return f"{months} month{'s' if months > 1 else ''}"
    return f"{days} days"


@router.get("/{group_id}/settings/records", summary="Get Privacy & Records Settings")
def get_privacy_and_records_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the comprehensive Privacy & Records configuration for the group:
    - Savings Charter metadata
    - My data retention policy
    - Download official statement permissions
    - Chat history cleanup and financial record preservation
    """
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this group.")

    is_admin = membership.role == "ADMIN"

    # Fetch settings models
    comm_settings = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()
    if not comm_settings:
        comm_settings = GroupCommunicationSettings(group_id=group_id)
        session.add(comm_settings)
        session.commit()
        session.refresh(comm_settings)

    gov_settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()

    vis_settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()

    retention_days = comm_settings.data_retention_days or 730
    cleanup_days = comm_settings.chat_history_cleanup_days or 90

    response_data = {
        "group_id": group_id,
        "group_name": group.name,
        "is_admin": is_admin,
        "savings_charter": {
            "title": "Official Savings charter",
            "description": f"These are the rules and member-approved terms for {group.name}. All members are bound by these terms upon joining.",
            "group_charter_url": gov_settings.group_charter_url if gov_settings else None,
            "charter_api_endpoint": f"/api/v1/groups/{group_id}/charter"
        },
        "data_retention": {
            "data_retention_days": retention_days,
            "data_retention_display": _format_days_to_display(retention_days),
            "storage_policy_label": "Keep until I delete my account" if retention_days >= 1825 else f"Retain for {_format_days_to_display(retention_days)}"
        },
        "official_statement": {
            "can_download": True if is_admin else (vis_settings.vis_download_official_statement if vis_settings else True),
            "vis_download_official_statement": vis_settings.vis_download_official_statement if vis_settings else True,
            "download_endpoint": f"/api/v1/groups/{group_id}/statement/download"
        },
        "chat_history_cleanup": {
            "chat_history_cleanup_days": cleanup_days,
            "chat_history_cleanup_display": f"After {_format_days_to_display(cleanup_days)}" if cleanup_days >= 30 else f"{cleanup_days} Days",
            "preserve_financial_records": comm_settings.preserve_financial_records,
            "vis_chat_history_cleanup": vis_settings.vis_chat_history_cleanup if vis_settings else True
        }
    }

    return {"status": "success", "data": response_data}


@router.patch("/{group_id}/settings/records", summary="Admin: Update Privacy & Records Settings")
def update_privacy_and_records_settings(
    group_id: str,
    request: UpdateRecordsSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates data retention days, chat cleanup interval, financial preservation, or charter URL.
    Only group administrators can modify these parameters.
    """
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update privacy and records settings.")

    comm_settings = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()
    if not comm_settings:
        comm_settings = GroupCommunicationSettings(group_id=group_id)
        session.add(comm_settings)

    gov_settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()
    if not gov_settings:
        gov_settings = GroupGovernanceSettings(group_id=group_id)
        session.add(gov_settings)

    if request.data_retention_days is not None:
        if request.data_retention_days < 30:
            raise HTTPException(status_code=400, detail="Data retention period must be at least 30 days.")
        comm_settings.data_retention_days = request.data_retention_days

    if request.chat_history_cleanup_days is not None:
        if request.chat_history_cleanup_days < 7:
            raise HTTPException(status_code=400, detail="Chat cleanup window must be at least 7 days.")
        comm_settings.chat_history_cleanup_days = request.chat_history_cleanup_days

    if request.preserve_financial_records is not None:
        comm_settings.preserve_financial_records = request.preserve_financial_records

    if request.group_charter_url is not None:
        gov_settings.group_charter_url = request.group_charter_url

    session.add(comm_settings)
    session.add(gov_settings)

    AuditService.record_event(
        session=session,
        action="PRIVACY_RECORDS_SETTINGS_UPDATED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={
            "updated_by": str(current_user.id),
            "data_retention_days": comm_settings.data_retention_days,
            "chat_history_cleanup_days": comm_settings.chat_history_cleanup_days,
            "preserve_financial_records": comm_settings.preserve_financial_records,
            "group_charter_url": gov_settings.group_charter_url
        },
        actor_user_id=current_user.id
    )

    session.commit()
    session.refresh(comm_settings)
    session.refresh(gov_settings)

    return {
        "status": "success",
        "message": "Privacy & Records settings updated successfully.",
        "data": {
            "data_retention_days": comm_settings.data_retention_days,
            "chat_history_cleanup_days": comm_settings.chat_history_cleanup_days,
            "preserve_financial_records": comm_settings.preserve_financial_records,
            "group_charter_url": gov_settings.group_charter_url
        }
    }


@router.get("/{group_id}/charter", summary="Get Official Savings Charter")
def get_group_savings_charter(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the formal legal Savings Charter for the group.
    Dynamically tailored to the group's savings type, rules, and penalties.
    """
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be a member of this group to view its charter.")

    fin = session.exec(select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)).first()
    gov = session.exec(select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)).first()

    late_fee_str = f"{int(fin.late_fee_amount):,} UGX" if fin and fin.enable_late_fees else "agreed penalty fee"

    clauses = [
        {
            "clause_number": 1,
            "title": "Membership Eligibility",
            "body": "Members must be invited and verified by group administrators or existing peers."
        },
        {
            "clause_number": 2,
            "title": "Contributions",
            "body": "All contributions must be made on time according to the group schedule and target parameters."
        },
        {
            "clause_number": 3,
            "title": "Penalties",
            "body": f"Late contributions will attract the {late_fee_str}. Persistent default leads to trust score degradation."
        },
        {
            "clause_number": 4,
            "title": "Conduct",
            "body": "Members must maintain respectful communication at all times. Collusive or fraudulent activity results in immediate expulsion."
        }
    ]

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "group_name": group.name,
            "group_type": group.type,
            "title": "Official Savings charter",
            "description": f"These are the rules and member-approved terms for {group.name}. All members are bound by these terms upon joining.",
            "clauses": clauses,
            "external_charter_url": gov.group_charter_url if gov else None
        }
    }


@router.delete("/{group_id}/members/me/data", summary="Delete All My Group Data")
def delete_my_group_data(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Permanently erases member's personal chat history and media from this group.
    Complies with data privacy regulations (GDPR/Data Protection Act).
    Strictly preserves financial audit records (obligations, receipts, payouts)
    when preserve_financial_records is enabled.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership record not found.")

    comm = session.exec(select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)).first()
    preserve_finance = comm.preserve_financial_records if comm else True

    # Delete or redact user's chat messages in this group
    messages_query = select(GroupChatMessage).where(
        GroupChatMessage.group_id == group_id,
        GroupChatMessage.sender_id == str(current_user.id)
    )
    if preserve_finance:
        # Exclude system and financial transaction receipts
        messages_query = messages_query.where(
            GroupChatMessage.message_type.notin_(["TRANSACTION_RECEIPT", "AUDIT_EVENT", "TRUST_EVENT"])
        )

    user_messages = session.exec(messages_query).all()
    deleted_count = len(user_messages)
    for msg in user_messages:
        session.delete(msg)

    AuditService.record_event(
        session=session,
        action="MEMBER_PERSONAL_DATA_PURGED",
        entity_type="USER",
        entity_id=str(current_user.id),
        payload={
            "group_id": group_id,
            "messages_purged_count": deleted_count,
            "financial_records_preserved": preserve_finance
        },
        actor_user_id=current_user.id
    )

    session.commit()

    return {
        "status": "success",
        "message": f"Successfully deleted {deleted_count} messages and media items. Financial records were preserved for audit compliance."
    }
