from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .constants import VALID_AVATAR_COLORS
from .schemas import AvatarColorRequest

router = APIRouter()


@router.patch("/me/avatar-color", summary="Update Fallback Avatar Color")
def update_avatar_color(
    payload: AvatarColorRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
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
