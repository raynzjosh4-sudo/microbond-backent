import io
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.services.cloud_storage import upload_bytes_to_r2, delete_file_from_r2
from .constants import ALLOWED_IMAGE_TYPES, MAX_AVATAR_SIZE_BYTES

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/me/avatar", summary="Upload & Update User Avatar")
async def upload_user_avatar(
    file: UploadFile = File(
        ..., description="Image file (JPEG, PNG, or WebP — max 5 MB)"
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    content_type = file.content_type or ""
    extension = ALLOWED_IMAGE_TYPES.get(content_type)
    if not extension:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: '{content_type}'. Allowed: JPEG, PNG, WebP.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the 5 MB limit ({len(file_bytes) // 1024} KB received).",
        )

    try:
        from PIL import Image

        with Image.open(io.BytesIO(file_bytes)) as img:
            img.verify()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupt image file. Please upload a valid JPEG, PNG, or WebP.",
        )

    avatar_url = await upload_bytes_to_r2(
        file_bytes=file_bytes,
        folder="avatars",
        content_type=content_type,
        extension=extension,
    )
    if not avatar_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image to cloud storage. Please try again.",
        )

    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    old_url = db_user.profile_picture_url
    if old_url and old_url.startswith(("http", "avatars/")):
        delete_file_from_r2(old_url)

    db_user.profile_picture_url = avatar_url
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    logger.info("Avatar updated for user %s → %s", current_user.id, avatar_url)

    return {
        "status": "success",
        "message": "Avatar uploaded and updated successfully.",
        "avatar_url": db_user.profile_picture_url,
        "profile_picture_url": db_user.profile_picture_url,
        "data": {
            "id": str(db_user.id),
            "user_id": str(db_user.id),
            "avatar_url": db_user.profile_picture_url,
            "profile_picture_url": db_user.profile_picture_url,
        },
    }
