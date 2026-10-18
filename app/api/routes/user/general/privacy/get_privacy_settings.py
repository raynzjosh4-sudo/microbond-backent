from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.services.privacy import normalize_privacy_setting
from .schemas import UserPrivacySettingsResponse

router = APIRouter()


@router.get("/me/privacy", response_model=UserPrivacySettingsResponse, summary="Get Current User Privacy Settings")
def get_user_privacy_settings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the personal privacy settings of the currently authenticated user.
    """
    db_user = session.get(User, current_user.id) or current_user
    return UserPrivacySettingsResponse(
        status="success",
        profile_photo_visibility=normalize_privacy_setting(
            getattr(db_user, "profile_photo_visibility", "EVERYONE")
        ),
        about_visibility=normalize_privacy_setting(
            getattr(db_user, "about_visibility", "EVERYONE")
        ),
        group_add_permission=normalize_privacy_setting(
            getattr(db_user, "group_add_permission", "EVERYONE")
        ),
    )
