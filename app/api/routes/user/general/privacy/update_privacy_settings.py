from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.services.privacy import normalize_privacy_setting, VALID_PRIVACY_OPTIONS
from .schemas import UpdateUserPrivacySettingsRequest, UserPrivacySettingsResponse

router = APIRouter()


@router.patch("/me/privacy", response_model=UserPrivacySettingsResponse, summary="Update Current User Privacy Settings")
def update_user_privacy_settings(
    request: UpdateUserPrivacySettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Updates one or more privacy settings for the current user.
    Accepted values: 'EVERYONE' / 'Everyone', 'MY_CONTACTS' / 'My contacts', 'NOBODY' / 'Nobody'.
    """
    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    if request.profile_photo_visibility is not None:
        normalized = normalize_privacy_setting(request.profile_photo_visibility)
        if normalized not in VALID_PRIVACY_OPTIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid profile_photo_visibility. Options: {', '.join(VALID_PRIVACY_OPTIONS)}",
            )
        db_user.profile_photo_visibility = normalized

    if request.about_visibility is not None:
        normalized = normalize_privacy_setting(request.about_visibility)
        if normalized not in VALID_PRIVACY_OPTIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid about_visibility. Options: {', '.join(VALID_PRIVACY_OPTIONS)}",
            )
        db_user.about_visibility = normalized

    if request.group_add_permission is not None:
        normalized = normalize_privacy_setting(request.group_add_permission)
        if normalized not in VALID_PRIVACY_OPTIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid group_add_permission. Options: {', '.join(VALID_PRIVACY_OPTIONS)}",
            )
        db_user.group_add_permission = normalized

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    return UserPrivacySettingsResponse(
        status="success",
        profile_photo_visibility=db_user.profile_photo_visibility,
        about_visibility=db_user.about_visibility,
        group_add_permission=db_user.group_add_permission,
    )
