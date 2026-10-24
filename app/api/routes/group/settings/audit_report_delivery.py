import logging
import csv
from io import StringIO
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership, Group
from app.models.group.settings import GroupCommunicationSettings, GroupGovernanceSettings
from app.models.group.finance import MemberObligation, GroupPayout
from app.services.communication.email_service import EmailNotificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Audit Ledger & Reporting"])


class UpdateAuditDeliverySettingsRequest(BaseModel):
    enable_automated_audit_dispatch: Optional[bool] = None
    audit_report_recipient_email: Optional[EmailStr] = None
    dispatch_monthly_compliance_statement: Optional[bool] = None
    export_file_format: Optional[str] = None


class ExportFinancialReportRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    export_format: Optional[str] = "PDF"  # "PDF" or "CSV"
    recipient_email: Optional[EmailStr] = None


@router.get(
    "/{group_id}/settings/audit-report-delivery",
    summary="Get Audit Report & Compliance Statement Delivery Settings",
    description="Returns current configuration for automated or on-demand delivery of audit statements."
)
def get_audit_report_delivery_settings(
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be an active member of this group to view audit delivery settings."
        )

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    settings = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()
    if not settings:
        settings = GroupCommunicationSettings(group_id=group_id)
        session.add(settings)
        session.commit()
        session.refresh(settings)

    group_name = getattr(group, "name", "Savings Group")

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "group_name": group_name,
            "enable_automated_audit_dispatch": settings.enable_automated_audit_dispatch,
            "audit_report_recipient_email": settings.audit_report_recipient_email,
            "dispatch_monthly_compliance_statement": settings.dispatch_monthly_compliance_statement,
            "export_file_format": settings.export_file_format or "PDF",
            "default_admin_email": current_user.backup_email if current_user.is_email_verified else None,
            "available_formats": ["PDF", "CSV"]
        }
    }


@router.patch(
    "/{group_id}/settings/audit-report-delivery",
    summary="Update Audit Report & Compliance Statement Delivery Settings",
    description="Updates settings for automated or on-demand delivery of group audit ledgers."
)
@router.put(
    "/{group_id}/settings/audit-report-delivery",
    summary="Update Audit Report & Compliance Statement Delivery Settings (PUT)",
    include_in_schema=False
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

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    settings = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()

    if not settings:
        settings = GroupCommunicationSettings(group_id=group_id)

    if request.enable_automated_audit_dispatch is not None:
        settings.enable_automated_audit_dispatch = request.enable_automated_audit_dispatch
    if request.audit_report_recipient_email is not None:
        settings.audit_report_recipient_email = request.audit_report_recipient_email
    if request.dispatch_monthly_compliance_statement is not None:
        settings.dispatch_monthly_compliance_statement = request.dispatch_monthly_compliance_statement
    if request.export_file_format is not None:
        settings.export_file_format = request.export_file_format.upper()

    session.add(settings)
    session.commit()
    session.refresh(settings)

    group_name = getattr(group, "name", "Savings Group")

    return {
        "status": "success",
        "message": "Audit report delivery settings updated successfully.",
        "data": {
            "group_id": group_id,
            "group_name": group_name,
            "enable_automated_audit_dispatch": settings.enable_automated_audit_dispatch,
            "audit_report_recipient_email": settings.audit_report_recipient_email,
            "dispatch_monthly_compliance_statement": settings.dispatch_monthly_compliance_statement,
            "export_file_format": settings.export_file_format
        }
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
                detail="No recipient email specified and no verified admin backup email found. Please configure a recipient email first."
            )

    group_name = getattr(group, "name", "Savings Group")
    fmt = (request.export_format or (settings.export_file_format if settings else "CSV")).upper()

    # Query obligations and payouts for compliance reconciliation
    obligations = session.exec(
        select(MemberObligation).where(MemberObligation.group_id == group_id)
    ).all()
    payouts = session.exec(
        select(GroupPayout).where(GroupPayout.group_id == group_id)
    ).all()

    total_due = sum(ob.amount_due for ob in obligations)
    total_paid = sum(ob.amount_paid for ob in obligations)
    total_expected_payouts = sum(p.amount_expected for p in payouts)
    total_received_payouts = sum(p.amount_received for p in payouts)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["MICROBOND COMPLIANCE AUDIT STATEMENT", ""])
    writer.writerow(["Group ID", group_id])
    writer.writerow(["Group Name", group_name])
    writer.writerow(["Currency", group.currency])
    writer.writerow(["Total Registered Members", group.member_count])
    writer.writerow(["Vault Ledger Balance", group.total_balance])
    writer.writerow([])
    writer.writerow(["TREASURY RECONCILIATION SUMMARY", ""])
    writer.writerow(["Total Obligations Billed", total_due])
    writer.writerow(["Total Contributions Collected", total_paid])
    writer.writerow(["Total Payouts Expected", total_expected_payouts])
    writer.writerow(["Total Payouts Disbursed", total_received_payouts])
    writer.writerow([])
    writer.writerow(["ITEMIZED MEMBER CONTRIBUTIONS", ""])
    writer.writerow(["User ID", "Cycle", "Status", "Amount Due", "Amount Paid"])
    for ob in obligations:
        writer.writerow([str(ob.user_id), ob.cycle_number, ob.status, ob.amount_due, ob.amount_paid])
    writer.writerow([])
    writer.writerow(["ITEMIZED GROUP DISBURSEMENTS / PAYOUTS", ""])
    writer.writerow(["User ID", "Cycle", "Status", "Amount Expected", "Amount Received"])
    for p in payouts:
        writer.writerow([str(p.user_id), p.cycle_number, p.status, p.amount_expected, p.amount_received])

    audit_bytes = output.getvalue().encode("utf-8")
    output.close()

    background_tasks.add_task(
        EmailNotificationService.send_audit_report,
        target_email,
        group_name,
        fmt,
        audit_bytes
    )

    return {
        "status": "success",
        "message": f"Audit compliance statement has been compiled and queued for delivery to {target_email}."
    }
