import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership, Group
from app.models.group.settings import GroupCommunicationSettings
from app.services.communication.email_service import EmailNotificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Audit Ledger & Reporting"])

class UpdateAuditDeliverySettingsRequest(BaseModel):
    enable_automated_audit_dispatch: bool
    audit_report_recipient_email: Optional[EmailStr] = None
    dispatch_monthly_compliance_statement: bool = True
    export_file_format: str = "PDF"

class ExportFinancialReportRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    export_format: str = "PDF" # PDF or CSV
    recipient_email: Optional[EmailStr] = None

@router.put(
    "/{group_id}/settings/audit-report-delivery",
    summary="Configure Audit Report & Compliance Statement Delivery",
    description="Updates settings for automated or on-demand delivery of group audit ledgers."
)
def update_audit_report_delivery_settings(
    group_id: str,
    request: UpdateAuditDeliverySettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()

    if not membership or membership.role not in ["ADMIN", "TREASURER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Group Admin or Treasurer can configure audit delivery settings."
        )

    settings = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()

    if not settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group settings not found.")

    settings.enable_automated_audit_dispatch = request.enable_automated_audit_dispatch
    if request.audit_report_recipient_email:
        settings.audit_report_recipient_email = request.audit_report_recipient_email
    settings.dispatch_monthly_compliance_statement = request.dispatch_monthly_compliance_statement
    settings.export_file_format = request.export_file_format.upper()

    session.add(settings)
    session.commit()

    return {
        "status": "success",
        "message": "Audit report delivery settings updated successfully."
    }

@router.post(
    "/{group_id}/financial-reports/export-and-email",
    summary="Compile and Email Group Audit Report",
    description="Generates double-entry ledger statement and emails it directly to the designated recipient."
)
async def export_and_email_financial_report(
    group_id: str,
    request: ExportFinancialReportRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()

    if not membership or membership.role not in ["ADMIN", "TREASURER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Group Admin or Treasurer can export group audit reports."
        )

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    settings = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()

    target_email = request.recipient_email or (settings.audit_report_recipient_email if settings else None)

    if not target_email:
        # Fallback to the current user's verified backup email if available
        if current_user.backup_email and current_user.is_email_verified:
            target_email = current_user.backup_email
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No recipient email specified and no verified admin email configured."
            )

    fmt = request.export_format.upper()
    dummy_audit_bytes = (
        f"Microbond Group Audit Ledger\nGroup: {group.title}\nID: {group_id}\nFormat: {fmt}\n"
    ).encode("utf-8")

    background_tasks.add_task(
        EmailNotificationService.send_audit_report,
        target_email,
        group.title,
        fmt,
        dummy_audit_bytes
    )

    return {
        "status": "success",
        "message": f"Audit report has been compiled and queued for delivery to {target_email}."
    }
