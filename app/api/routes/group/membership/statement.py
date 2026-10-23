from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, select
from typing import Optional
from io import StringIO
import csv

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.finance import MemberObligation, GroupPayout
from app.models.group.settings import GroupVisibilitySettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Statements"])

@router.get("/{group_id}/statement/download", summary="Download Official Statement")
def download_official_statement(
    group_id: str,
    period_days: int = Query(default=30, description="Statement period in days (e.g. 30)"),
    format: str = Query(default="pdf", description="Format: 'pdf' or 'csv'"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Downloads an official statement of obligations and payouts.
    Respects the admin's vis_member_total_savings toggle — when disabled,
    non-admin members cannot download their savings statement.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this group.")

    # Check admin visibility settings
    vis_settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()

    is_admin = (membership.role == "ADMIN")
    savings_visible = getattr(vis_settings, "vis_member_total_savings", True) if vis_settings else True
    statement_visible = vis_settings.vis_download_official_statement if vis_settings else True

    if not is_admin and (not savings_visible or not statement_visible):
        raise HTTPException(
            status_code=403,
            detail="The Group Admin has restricted members from viewing or downloading their savings statements."
        )

    # Retrieve member records
    obligations = session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == group_id,
            MemberObligation.user_id == current_user.id
        )
    ).all()

    payouts = session.exec(
        select(GroupPayout).where(
            GroupPayout.group_id == group_id,
            GroupPayout.user_id == current_user.id
        )
    ).all()

    # For now, we will generate a CSV response regardless of the format request,
    # as PDF generation requires heavy external libraries (like ReportLab or WeasyPrint).

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Type", "Cycle Number", "Status", "Amount Due/Expected", "Amount Paid/Received"])

    for ob in obligations:
        writer.writerow(["Contribution", ob.cycle_number, ob.status, ob.amount_due, ob.amount_paid])

    for pay in payouts:
        writer.writerow(["Payout", pay.cycle_number, pay.status, pay.amount_expected, pay.amount_received])

    csv_content = output.getvalue()
    output.close()

    # Send as downloadable file
    response = Response(content=csv_content, media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=Group_{group_id}_Statement_Last_{period_days}Days.csv"

    return response
