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

class UpdateRecordsVisibilityRequest(BaseModel):
    vis_member_total_savings: Optional[bool] = None
    vis_download_official_statement: Optional[bool] = None
    vis_chat_history_cleanup: Optional[bool] = None

@router.patch("/{group_id}/settings/records-visibility", summary="Admin: Update Privacy & Records Visibility")
def update_records_visibility_settings(
    group_id: str, 
    request: UpdateRecordsVisibilityRequest, 
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

    if request.vis_member_total_savings is not None:
        settings.vis_member_total_savings = request.vis_member_total_savings
    if request.vis_download_official_statement is not None:
        settings.vis_download_official_statement = request.vis_download_official_statement
    if request.vis_chat_history_cleanup is not None:
        settings.vis_chat_history_cleanup = request.vis_chat_history_cleanup

    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Privacy & Records visibility updated successfully."}
