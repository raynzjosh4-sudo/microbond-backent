from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.models.user.user import User
from app.core.database import get_session
from app.services.privacy import can_view_profile_photo, can_view_about_status

router = APIRouter()


@router.get("/{phone_number}/status", summary="Get User Profile Status")
def get_user_status(phone_number: str, session: Session = Depends(get_session)):
    clean_phone = phone_number.strip().replace(" ", "").replace("-", "")
    if clean_phone.startswith("0"):
        normalized_phone = "+256" + clean_phone[1:]
    elif clean_phone.startswith("256"):
        normalized_phone = "+" + clean_phone
    elif not clean_phone.startswith("+"):
        normalized_phone = "+" + clean_phone
    else:
        normalized_phone = clean_phone

    alt_phone = normalized_phone.lstrip("+")
    statement = select(User).where(
        (User.phone_number == normalized_phone)
        | (User.phone_number == alt_phone)
    )
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Privacy guards for unauthenticated public status lookup
    photo_allowed = can_view_profile_photo(
        user, viewer_user_id=None, is_contact=False, shares_group=False
    )
    about_allowed = can_view_about_status(
        user, viewer_user_id=None, is_contact=False, shares_group=False
    )

    from app.utils.avatar_colors import resolve_vibrant_avatar_color
    return {
        "status": "success",
        "user_id": user.id,
        "phone_number": user.phone_number,
        "is_phone_verified": user.is_phone_verified,
        "is_profile_complete": user.is_profile_complete,
        "kyc_tier": user.kyc_tier,
        "full_name": user.full_name,
        "profile_picture_url": user.profile_picture_url if photo_allowed else None,
        "avatar_color": resolve_vibrant_avatar_color(user.avatar_color, seed=user.phone_number or str(user.id)),
        "about_status": user.about_status if about_allowed else None,
    }
