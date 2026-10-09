from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session
from uuid import UUID

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group
from app.models.group.report import GroupReport

router = APIRouter(prefix="/api/v1/groups", tags=["Group Reporting"])

class SubmitReportRequest(BaseModel):
    reason: str
    description: Optional[str] = None

@router.post("/{group_id}/report", summary="Send a private report to support about this group")
def report_group(
    group_id: str,
    request: SubmitReportRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Check if the group exists
    group = session.query(Group).filter_by(group_id=group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    # 2. Prevent spam: Check if this user recently reported this group
    existing_report = session.query(GroupReport).filter_by(
        group_id=group_id,
        reporter_user_id=current_user.id,
        status="OPEN"
    ).first()
    
    if existing_report:
        raise HTTPException(
            status_code=400, 
            detail="You already have an open report for this group. Support is reviewing it."
        )

    # 3. Create the report
    new_report = GroupReport(
        group_id=group_id,
        reporter_user_id=current_user.id,
        reason=request.reason,
        description=request.description,
        status="OPEN"
    )
    
    session.add(new_report)
    session.commit()
    
    # In a real app, this might trigger an email or push a message to a Slack/Discord channel for support staff.
    
    return {
        "status": "success", 
        "message": "Thank you for keeping Microbond safe. Your report has been submitted to support for review."
    }
