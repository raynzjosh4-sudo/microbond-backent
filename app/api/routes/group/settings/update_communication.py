from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupCommunicationSettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateCommunicationSettingsRequest(BaseModel):
    # Records & Cleanup
    data_retention_days: Optional[int] = None
    chat_history_cleanup_days: Optional[int] = None
    preserve_financial_records: Optional[bool] = None

@router.patch("/{group_id}/settings/communication", summary="Admin: Update Communication & Record Settings")
def update_communication_settings(
    group_id: str, 
    request: UpdateCommunicationSettingsRequest, 
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
        raise HTTPException(status_code=403, detail="Only the Group Admin can update these settings.")

    settings = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found.")

    if request.data_retention_days is not None:
        if request.data_retention_days < 30:
            raise HTTPException(status_code=400, detail="Data retention must be at least 30 days.")
        settings.data_retention_days = request.data_retention_days
        
    if request.chat_history_cleanup_days is not None:
        if request.chat_history_cleanup_days < 7:
            raise HTTPException(status_code=400, detail="Chat history cleanup must be at least 7 days.")
        settings.chat_history_cleanup_days = request.chat_history_cleanup_days
        
    if request.preserve_financial_records is not None:
        settings.preserve_financial_records = request.preserve_financial_records

    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Communication & Record settings updated successfully."}
