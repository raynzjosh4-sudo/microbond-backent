from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from typing import Optional
import uuid

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.kyc import KycProfile

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

class UpdateUserProfileRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100, description="New full name, e.g. 'SSENKINDU EMMANUEL'")
    profile_picture_url: Optional[str] = Field(default=None, description="Direct URL to uploaded profile picture")
    avatar_color: Optional[str] = Field(default=None, description="Profile fallback avatar color, e.g. 'Blue', 'Emerald'")
    about_status: Optional[str] = Field(default=None, max_length=160, description="User status / bio message")

class UpdateUserNameRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="New full name, e.g. 'SSENKINDU EMMANUEL'")

@router.patch("/me/profile", summary="Update Current User Profile Details")
def update_current_user_profile(
    request: UpdateUserProfileRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the authenticated user's profile details including:
    - full_name (synced to KycProfile)
    - profile_picture_url
    - avatar_color
    - about_status
    """
    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    if request.full_name is not None:
        clean_name = request.full_name.strip()
        if len(clean_name) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Full name must be at least 2 characters long."
            )
        db_user.full_name = clean_name

        # Sync KycProfile
        kyc_profile = session.exec(
            select(KycProfile).where(KycProfile.user_id == db_user.id)
        ).first()

        if kyc_profile:
            parts = clean_name.split()
            kyc_profile.first_name = parts[0]
            kyc_profile.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
            kyc_profile.sim_registered_name = clean_name
            session.add(kyc_profile)

    if request.profile_picture_url is not None:
        db_user.profile_picture_url = request.profile_picture_url.strip() or None

    if request.avatar_color is not None:
        db_user.avatar_color = request.avatar_color.strip()

    if request.about_status is not None:
        db_user.about_status = request.about_status.strip()

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
            "kyc_tier": db_user.kyc_tier
        }
    }

@router.patch("/me/name", summary="Update Current User Full Name")
def update_current_user_name(
    request: UpdateUserNameRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the authenticated user's full name.
    Also synchronizes the name with their KycProfile.
    """
    clean_name = request.full_name.strip()
    if len(clean_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Full name must be at least 2 characters long."
        )

    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    db_user.full_name = clean_name
    session.add(db_user)

    # Sync KycProfile if present
    kyc_profile = session.exec(
        select(KycProfile).where(KycProfile.user_id == db_user.id)
    ).first()

    if kyc_profile:
        parts = clean_name.split()
        kyc_profile.first_name = parts[0]
        kyc_profile.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        kyc_profile.sim_registered_name = clean_name
        session.add(kyc_profile)

    session.commit()
    session.refresh(db_user)

    return {
        "status": "success",
        "message": "User name updated successfully.",
        "data": {
            "user_id": str(db_user.id),
            "full_name": db_user.full_name,
            "phone_number": db_user.phone_number,
            "kyc_tier": db_user.kyc_tier
        }
    }

@router.patch("/{user_id}/name", summary="Update User Name by ID")
def update_user_name_by_id(
    user_id: str,
    request: UpdateUserNameRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates a user's full name by user UUID.
    """
    clean_name = request.full_name.strip()
    if len(clean_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Full name must be at least 2 characters long."
        )

    try:
        target_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user UUID format.")

    if current_user.id != target_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You can only update your own user name."
        )

    target_user = session.get(User, target_uuid)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    target_user.full_name = clean_name
    session.add(target_user)

    kyc_profile = session.exec(
        select(KycProfile).where(KycProfile.user_id == target_user.id)
    ).first()

    if kyc_profile:
        parts = clean_name.split()
        kyc_profile.first_name = parts[0]
        kyc_profile.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        kyc_profile.sim_registered_name = clean_name
        session.add(kyc_profile)

    session.commit()
    session.refresh(target_user)

    return {
        "status": "success",
        "message": "User name updated successfully.",
        "data": {
            "user_id": str(target_user.id),
            "full_name": target_user.full_name,
            "phone_number": target_user.phone_number,
            "kyc_tier": target_user.kyc_tier
        }
    }
