from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.kyc import KycProfile
from .schemas import UpdateUserProfileRequest

router = APIRouter()


@router.patch("/me/profile", summary="Update Current User Profile Details")
@router.put("/me/profile", summary="Update Current User Profile Details (PUT alias)")
@router.patch("/me", summary="Update Current User Profile Details (PATCH /me alias)")
@router.put("/me", summary="Update Current User Profile Details (PUT /me alias)")
def update_current_user_profile(
    request: UpdateUserProfileRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    if request.full_name is not None:
        clean_name = request.full_name.strip()
        if len(clean_name) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Full name must be at least 2 characters long.",
            )
        db_user.full_name = clean_name

        # Sync KycProfile
        kyc_profile = session.exec(
            select(KycProfile).where(KycProfile.user_id == db_user.id)
        ).first()

        if kyc_profile:
            parts = clean_name.split()
            kyc_profile.first_name = parts[0]
            kyc_profile.last_name = (
                " ".join(parts[1:]) if len(parts) > 1 else ""
            )
            kyc_profile.sim_registered_name = clean_name
            session.add(kyc_profile)

    if request.profile_picture_url is not None:
        db_user.profile_picture_url = (
            request.profile_picture_url.strip() or None
        )

    if request.avatar_color is not None:
        db_user.avatar_color = request.avatar_color.strip()

    if request.about_status is not None:
        db_user.about_status = request.about_status.strip()

    # Mark profile as completed once full name is provided
    if db_user.full_name and len(db_user.full_name.strip()) >= 2:
        db_user.is_profile_complete = True

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    return {
        "status": "success",
        "message": "User profile updated successfully.",
        "data": {
            "user_id": str(db_user.id),
            "full_name": db_user.full_name,
            "phone_number": db_user.phone_number,
            "profile_picture_url": db_user.profile_picture_url,
            "avatar_color": db_user.avatar_color,
            "about_status": db_user.about_status,
            "is_profile_complete": db_user.is_profile_complete,
            "kyc_tier": db_user.kyc_tier,
        },
    }
