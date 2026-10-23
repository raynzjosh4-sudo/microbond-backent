import io
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks
from pydantic import BaseModel
from sqlmodel import Session, select
from PIL import Image

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupGovernanceSettings
from app.models.group.chat import GroupChatMessage
from app.services.cloud_storage import upload_bytes_to_r2, delete_file_from_r2
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class GroupImageResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


@router.post("/{group_id}/settings/image", response_model=GroupImageResponse, summary="Upload Group Image to Cloudflare R2")
@router.post("/{group_id}/avatar", response_model=GroupImageResponse, summary="Upload Group Avatar (Alias)")
async def upload_group_image(
    group_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Image file (JPEG, PNG, or WebP — max 5 MB)"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Upload and set group avatar / icon directly to Cloudflare R2.
    Permissions:
    - User must be an ACTIVE member of the group.
    - If user is not an ADMIN, `members_can_edit_settings` must be True in GroupGovernanceSettings.
    """
    content_type = file.content_type or ""
    extension = ALLOWED_IMAGE_TYPES.get(content_type)
    if not extension and file.filename:
        file_ext = file.filename.rsplit(".", 1)[-1].lower()
        if file_ext in ["jpg", "jpeg"]:
            extension = "jpg"
            content_type = "image/jpeg"
        elif file_ext == "png":
            extension = "png"
            content_type = "image/png"
        elif file_ext == "webp":
            extension = "webp"
            content_type = "image/webp"

    if not extension:
        try:
            with Image.open(io.BytesIO(file_bytes)) as test_img:
                fmt = (test_img.format or "").lower()
                if fmt in ["jpeg", "jpg"]:
                    extension = "jpg"
                    content_type = "image/jpeg"
                elif fmt == "png":
                    extension = "png"
                    content_type = "image/png"
                elif fmt == "webp":
                    extension = "webp"
                    content_type = "image/webp"
        except Exception:
            pass

    if not extension:
        extension = "jpg"
        content_type = "image/jpeg" 

    file_bytes = await file.read()
    if len(file_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the 5 MB limit ({len(file_bytes) // 1024} KB received).",
        )

    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img.verify()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupt image file. Please upload a valid JPEG, PNG, or WebP.",
        )

    # 1. Fetch group with row lock (by UUID or name)
    group = session.exec(
        select(Group).where(
            (Group.group_id == group_id) | (Group.name == group_id)
        ).with_for_update()
    ).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    # 2. Check active membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE",
        )
    ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this group.",
        )

    # 3. Check governance permissions
    governance_settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group.group_id)
    ).first()

    if membership.role != "ADMIN":
        if not governance_settings or not governance_settings.members_can_edit_settings:
            logger.warning(
                f"Non-admin user {current_user.id} attempted to upload group image for {group_id} without permission."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Group settings restrict profile updates to ADMIN members only.",
            )

    # 4. Upload bytes to Cloudflare R2
    new_image_url = await upload_bytes_to_r2(
        file_bytes=file_bytes,
        folder=f"groups/{group.group_id}/avatar",
        content_type=content_type,
        extension=extension,
    )
    if not new_image_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image to cloud storage. Please try again.",
        )

    # 5. Clean up old image from R2 if present
    old_image_url = group.group_image_url
    if old_image_url and old_image_url != new_image_url:
        background_tasks.add_task(delete_file_from_r2, old_image_url)

    # 6. Update database record
    group.group_image_url = new_image_url
    session.add(group)

    try:
        session.commit()
        session.refresh(group)

        # 7. Publish system chat event & broadcast via WebSocket
        system_text = f"{current_user.full_name} updated the group icon."
        system_message = GroupChatMessage(
            client_message_id=str(uuid.uuid4()),
            group_id=group_id,
            sender_id=str(current_user.id),
            message_type="SYSTEM_EVENT",
            message_text=system_text,
            media_url=new_image_url,
            media_type="IMAGE",
            status="SENT",
        )
        session.add(system_message)
        session.commit()
        session.refresh(system_message)

        background_tasks.add_task(
            ws_manager.broadcast_to_group,
            group_id,
            {
                "event_type": "NEW_MESSAGE",
                "message": system_message.model_dump(mode="json"),
            },
        )
        background_tasks.add_task(
            ws_manager.broadcast_to_group,
            group_id,
            {
                "event_type": "GROUP_PROFILE_UPDATED",
                "group_id": group_id,
                "group_image_url": new_image_url,
            },
        )

    except Exception as e:
        session.rollback()
        logger.exception(f"Failed to save group image for {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update group image due to an internal database error.",
        )

    return {
        "status": "success",
        "message": "Group icon updated successfully.",
        "data": {
            "group_id": group.group_id,
            "group_image_url": group.group_image_url,
            "updated_at": group.updated_at,
        },
    }


@router.delete("/{group_id}/settings/image", response_model=GroupImageResponse, summary="Remove Group Image")
@router.delete("/{group_id}/avatar", response_model=GroupImageResponse, summary="Remove Group Avatar (Alias)")
def remove_group_image(
    group_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Removes the group's current image / avatar and resets it to None.
    Same permission rules as upload.
    """
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
            GroupMembership.status == "ACTIVE",
        )
    ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this group.",
        )

    governance_settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group.group_id)
    ).first()

    if membership.role != "ADMIN":
        if not governance_settings or not governance_settings.members_can_edit_settings:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Group settings restrict profile updates to ADMIN members only.",
            )

    old_image_url = group.group_image_url
    if not old_image_url:
        return {
            "status": "success",
            "message": "Group does not have a custom image.",
            "data": {
                "group_id": group.group_id,
                "group_image_url": None,
                "updated_at": group.updated_at,
            },
        }

    # Delete from R2
    background_tasks.add_task(delete_file_from_r2, old_image_url)

    group.group_image_url = None
    session.add(group)

    try:
        session.commit()
        session.refresh(group)

        system_text = f"{current_user.full_name} removed the group icon."
        system_message = GroupChatMessage(
            client_message_id=str(uuid.uuid4()),
            group_id=group_id,
            sender_id=str(current_user.id),
            message_type="SYSTEM_EVENT",
            message_text=system_text,
            status="SENT",
        )
        session.add(system_message)
        session.commit()

        background_tasks.add_task(
            ws_manager.broadcast_to_group,
            group_id,
            {
                "event_type": "NEW_MESSAGE",
                "message": system_message.model_dump(mode="json"),
            },
        )
        background_tasks.add_task(
            ws_manager.broadcast_to_group,
            group_id,
            {
                "event_type": "GROUP_PROFILE_UPDATED",
                "group_id": group_id,
                "group_image_url": None,
            },
        )
    except Exception as e:
        session.rollback()
        logger.exception(f"Failed to reset group image for {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset group image due to an internal error.",
        )

    return {
        "status": "success",
        "message": "Group icon removed successfully.",
        "data": {
            "group_id": group.group_id,
            "group_image_url": None,
            "updated_at": group.updated_at,
        },
    }
