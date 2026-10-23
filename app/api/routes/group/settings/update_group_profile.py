from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel, Field
import logging

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupGovernanceSettings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateGroupProfileRequest(BaseModel):
    name: Optional[str] = Field(default=None, description="The new name of the group", min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, description="The new description of the group", max_length=500)
    group_image_url: Optional[str] = Field(default=None, description="The new image URL of the group")

class UpdateGroupProfileResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None

@router.patch("/{group_id}/settings/profile", response_model=UpdateGroupProfileResponse, summary="Update Group Profile (Name, Image, Description)")
def update_group_profile(
    group_id: str,
    request: UpdateGroupProfileRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update the group's name, description, and image.
    Access control is determined by the `members_can_edit_settings` governance setting.
    If False, only ADMINs can update this info. If True, any ACTIVE member can.
    """
    # 1. Validation: Prevent empty updates
    if request.name is None and request.description is None and request.group_image_url is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="At least one field (name, description, or group_image_url) must be provided."
        )

    # 2. Concurrency Control: Lock the row for update (by UUID or name)
    group = session.exec(
        select(Group).where(
            (Group.group_id == group_id) | (Group.name == group_id)
        ).with_for_update()
    ).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")
        
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not an active member of this group.")

    # 3. Authorization: Check governance settings for profile updates
    governance_settings = session.exec(select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group.group_id)).first()
    
    if membership.role != "ADMIN":
        if not governance_settings or not governance_settings.members_can_edit_settings:
            logger.warning(f"Non-admin user {current_user.id} attempted to edit group profile {group_id} without permission.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Group settings restrict profile updates to ADMIN members only."
            )

    # 4. Processing: Apply updates
    changes = []
    if request.name is not None and request.name != group.name:
        changes.append(f"name to '{request.name}'")
        group.name = request.name
    if request.description is not None and request.description != group.description:
        changes.append("description")
        group.description = request.description
    if request.group_image_url is not None and request.group_image_url != group.group_image_url:
        changes.append("image")
        group.group_image_url = request.group_image_url
        
    session.add(group)
    
    try:
        session.commit()
        session.refresh(group)
        
        # --- CHAT INTEGRATION ---
        if changes:
            import uuid
            from app.models.group.chat import GroupChatMessage
            from app.services.websocket_manager import ws_manager
            
            changes_str = " and ".join(changes)
            system_text = f"{current_user.full_name} changed the group {changes_str}."
            
            chat_media_url = request.group_image_url if (request.group_image_url is not None and "image" in changes) else None
            chat_media_type = "IMAGE" if chat_media_url else None

            system_message = GroupChatMessage(
                client_message_id=str(uuid.uuid4()),
                group_id=group_id,
                sender_id=str(current_user.id),
                message_type="SYSTEM_EVENT",
                message_text=system_text,
                media_url=chat_media_url,
                media_type=chat_media_type,
                status="SENT"
            )
            session.add(system_message)
            session.commit()
            session.refresh(system_message)
            
            # Broadcast the system message to active users in the background
            background_tasks.add_task(
                ws_manager.broadcast_to_group,
                group_id,
                {
                    "event_type": "NEW_MESSAGE",
                    "message": system_message.model_dump()
                }
            )
            
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update group profile for {group_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update group profile due to an internal error.")

    # 5. Response
    return {
        "status": "success", 
        "message": "Group profile updated successfully.",
        "data": {
            "name": group.name,
            "description": group.description,
            "group_image_url": group.group_image_url,
            "updated_at": group.updated_at
        }
    }
