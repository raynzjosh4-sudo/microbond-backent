from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlmodel import Session
import io
import logging

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.services.cloud_storage import upload_bytes_to_r2, delete_file_from_r2

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

VALID_AVATAR_COLORS = {
    "Slate", "Gray", "Zinc", "Stone", "Red", "Orange", "Amber",
    "Yellow", "Lime", "Green", "Emerald", "Teal", "Cyan", "Sky",
    "Blue", "Indigo", "Violet", "Purple", "Fuchsia", "Pink", "Rose",
}


class AvatarColorRequest(BaseModel):
    color: str


# ---------------------------------------------------------------------------
# POST /api/v1/users/me/avatar
# Upload & replace profile picture (multipart)
# ---------------------------------------------------------------------------

@router.post("/me/avatar", summary="Upload & Update User Avatar")
async def upload_user_avatar(
    file: UploadFile = File(..., description="Image file (JPEG, PNG, or WebP — max 5 MB)"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Replaces the user's profile picture with a new image uploaded directly to Cloudflare R2.

    Pipeline:
      1. Validates MIME type (JPEG / PNG / WebP only)
      2. Reads full bytes and enforces 5 MB limit
      3. Verifies the image is not corrupt using Pillow
      4. Uploads validated bytes to R2 under 'avatars/' folder
         (uses upload_bytes_to_r2 — avoids the PIL seek-invalidation bug)
      5. Deletes the old avatar object from R2 if one existed
      6. Writes the new CDN URL to the User record
    """
    # ── 1. MIME type guard ───────────────────────────────────────────────────
    content_type = file.content_type or ""
    extension = ALLOWED_IMAGE_TYPES.get(content_type)
    if not extension:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: '{content_type}'. Allowed: JPEG, PNG, WebP.",
        )

    # ── 2. Read into memory & enforce size cap ───────────────────────────────
    file_bytes = await file.read()
    if len(file_bytes) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the 5 MB limit ({len(file_bytes) // 1024} KB received).",
        )

    # ── 3. Structural image validation (Pillow) ──────────────────────────────
    # NOTE: img.verify() consumes the stream AND closes it, so we must work
    # from file_bytes (in-memory) rather than re-seeking the UploadFile object.
    try:
        from PIL import Image
        with Image.open(io.BytesIO(file_bytes)) as img:
            img.verify()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupt image file. Please upload a valid JPEG, PNG, or WebP.",
        )

    # ── 4. Upload validated bytes to R2 ─────────────────────────────────────
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

    # ── 5. Delete the old avatar from R2 (prevents orphaned objects) ─────────
    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    old_url = db_user.profile_picture_url
    if old_url and old_url.startswith(("http", "avatars/")):
        delete_file_from_r2(old_url)

    # ── 6. Persist new URL ───────────────────────────────────────────────────
    db_user.profile_picture_url = avatar_url
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    logger.info("Avatar updated for user %s → %s", current_user.id, avatar_url)

    return {
        "status": "success",
        "message": "Avatar uploaded and updated successfully.",
        "data": {
            "user_id": str(db_user.id),
            "profile_picture_url": db_user.profile_picture_url,
        },
    }


# ---------------------------------------------------------------------------
# DELETE /api/v1/users/me/avatar
# Remove profile picture, fall back to avatar color
# ---------------------------------------------------------------------------

@router.delete("/me/avatar", summary="Remove User Avatar")
def remove_user_avatar(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Removes the user's profile picture and deletes the object from R2.
    The mobile app should fall back to the user's avatar_color initials tile.
    """
    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    old_url = db_user.profile_picture_url
    if not old_url:
        return {
            "status": "success",
            "message": "No avatar to remove.",
            "data": {"user_id": str(db_user.id), "avatar_color": db_user.avatar_color},
        }

    # Delete from R2 first, then clear the DB reference
    delete_file_from_r2(old_url)

    db_user.profile_picture_url = None
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    logger.info("Avatar removed for user %s", current_user.id)

    return {
        "status": "success",
        "message": "Avatar removed. Fallback color is active.",
        "data": {
            "user_id": str(db_user.id),
            "profile_picture_url": None,
            "avatar_color": db_user.avatar_color,
        },
    }


# ---------------------------------------------------------------------------
# PATCH /api/v1/users/me/avatar-color
# Update fallback avatar color (shown when no photo is set)
# ---------------------------------------------------------------------------

@router.patch("/me/avatar-color", summary="Update Fallback Avatar Color")
def update_avatar_color(
    payload: AvatarColorRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Updates the avatar background color used as a fallback when the user has
    no profile picture set. The mobile app renders this as a colored initials tile.

    Accepted values: Slate, Gray, Red, Orange, Amber, Yellow, Lime, Green,
    Emerald, Teal, Cyan, Sky, Blue, Indigo, Violet, Purple, Fuchsia, Pink, Rose.
    """
    color = payload.color.strip().capitalize()
    if color not in VALID_AVATAR_COLORS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid color '{payload.color}'. Choose from: {', '.join(sorted(VALID_AVATAR_COLORS))}.",
        )

    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    db_user.avatar_color = color
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    return {
        "status": "success",
        "message": f"Avatar color updated to {color}.",
        "data": {
            "user_id": str(db_user.id),
            "avatar_color": db_user.avatar_color,
            "profile_picture_url": db_user.profile_picture_url,
        },
    }
