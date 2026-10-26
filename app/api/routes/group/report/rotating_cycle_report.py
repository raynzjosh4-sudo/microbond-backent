from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, select
from typing import Optional, List, Dict, Any

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.report.rotating_cycle_report import RotatingCycleReport
from app.services.group.rotating.rotating_report_service import (
    build_cycle_report_payload,
    generate_and_save_cycle_report,
    generate_printable_html,
    generate_csv,
)

router = APIRouter(prefix="/api/v1/groups", tags=["Rotating Group Reports"])


def _verify_membership(session: Session, group_id: str, user_id: Any) -> GroupMembership:
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Access denied. You are not an active member of this group.")
    return membership


@router.get("/{group_id}/reports/cycles", summary="List Rotating Group Cycle Reports")
def list_cycle_reports(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Lists all official cycle completion milestone reports recorded for this group.
    """
    _verify_membership(session, group_id, current_user.id)

    reports = session.exec(
        select(RotatingCycleReport)
        .where(RotatingCycleReport.group_id == group_id)
        .order_by(RotatingCycleReport.cycle_number.desc())
    ).all()

    return {
        "status": "success",
        "data": [
            {
                "report_id": r.report_id,
                "cycle_number": r.cycle_number,
                "expected_pool_target": r.expected_pool_target,
                "actual_collected_amount": r.actual_collected_amount,
                "collection_rate_percentage": r.collection_rate_percentage,
                "gross_payout_amount": r.gross_payout_amount,
                "early_security_hold_deducted": r.early_security_hold_deducted,
                "net_payout_disbursed": r.net_payout_disbursed,
                "recipient_name": r.recipient_name,
                "recipient_turn_position": r.recipient_turn_position,
                "cryptographic_hash_sha256": r.cryptographic_hash_sha256,
                "ledger_entries_count": r.ledger_entries_count,
                "generated_at": r.generated_at
            }
            for r in reports
        ]
    }


@router.get("/{group_id}/reports/cycle/{cycle_number}", summary="Get Detailed Rotating Cycle Milestone Report")
def get_cycle_report(
    group_id: str,
    cycle_number: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the comprehensive, cryptographically sealed Cycle Milestone Statement
    conforming to the Rotating Group Reporting & Audit Ledger specification.
    """
    _verify_membership(session, group_id, current_user.id)

    # Check for persisted report
    report = session.exec(
        select(RotatingCycleReport).where(
            RotatingCycleReport.group_id == group_id,
            RotatingCycleReport.cycle_number == cycle_number
        )
    ).first()

    if report and report.report_data:
        return {
            "status": "success",
            "data": report.report_data
        }

    # If not already persisted, generate live
    try:
        data = build_cycle_report_payload(session, group_id, cycle_number)
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{group_id}/reports/cycle/{cycle_number}/export", summary="Export Cycle Report (HTML / CSV / JSON)")
def export_cycle_report(
    group_id: str,
    cycle_number: int,
    format: str = Query("html", description="Export format: html, csv, or json"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Exports the verified Cycle Milestone Statement as printable HTML (for PDF printing)
    or CSV for audit spreadsheets.
    """
    _verify_membership(session, group_id, current_user.id)

    report = session.exec(
        select(RotatingCycleReport).where(
            RotatingCycleReport.group_id == group_id,
            RotatingCycleReport.cycle_number == cycle_number
        )
    ).first()

    if report and report.report_data:
        report_data = report.report_data
    else:
        try:
            report_data = build_cycle_report_payload(session, group_id, cycle_number)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    fmt = format.lower()
    if fmt == "csv":
        csv_content = generate_csv(report_data)
        filename = f"rotating_cycle_{cycle_number}_{group_id[:8]}_statement.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt == "json":
        return {"status": "success", "data": report_data}
    else:
        # Default: printable HTML
        html_content = generate_printable_html(report_data)
        return Response(content=html_content, media_type="text/html")
