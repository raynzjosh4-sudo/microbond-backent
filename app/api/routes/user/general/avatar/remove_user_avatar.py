import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.services.cloud_storage import delete_file_from_r2

logger = logging.getLogger(__name__)

router = APIRouter()


@router.delete("/me/avatar", summary="Remove User Avatar")
def remove_user_avatar(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    old_url = db_user.profile_picture_url
    if not old_url:
        return {
            "status": "success",
            "message": "No avatar to remove.",
            "data": {
                "user_id": str(db_user.id),
                "avatar_color": db_user.avatar_color,
            },
        }

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
