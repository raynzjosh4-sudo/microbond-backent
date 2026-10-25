from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.models.user.user import User
from app.api.dependencies import get_current_firebase_user
from app.core.database import get_session
from app.core.security import create_access_token

router = APIRouter()

@router.post(
    "/verify",
    summary="Verify Firebase Token",
    description="Verifies a Firebase JWT token sent from the Android app. If valid, logs the user in or registers a new user in the PostgreSQL database based on their Firebase UID."
)
def verify_otp_login(
    decoded_token: dict = Depends(get_current_firebase_user),
    session: Session = Depends(get_session)
):
    firebase_uid = decoded_token.get("uid")
    phone_number = decoded_token.get("phone_number")

    if not phone_number:
        raise HTTPException(
            status_code=400, 
            detail="Firebase token does not contain a verified phone number."
        )

    # Query existing user in Supabase
    statement = select(User).where(User.phone_number == phone_number)
    user = session.exec(statement).first()
    is_new_user = False

    if not user:
        from app.utils.avatar_colors import pick_random_avatar_color
        # Create a new user record on first login
        user = User(
            firebase_uid=firebase_uid,
            phone_number=phone_number,
            is_phone_verified=True,
            is_profile_complete=False,
            avatar_color=pick_random_avatar_color()
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        is_new_user = True

    # Generate our own internal JWT token for subsequent API requests
    access_token = create_access_token(data={"sub": str(user.id), "phone": user.phone_number})

    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "firebase_uid": user.firebase_uid,
        "phone_number": user.phone_number,
        "is_new_user": is_new_user,
        "is_profile_complete": user.is_profile_complete,
        "has_app_pin": bool(user.hashed_pin is not None),
        "full_name": user.full_name,
        "avatar_url": user.profile_picture_url,
        "profile_picture_url": user.profile_picture_url,
        "avatar_color": user.avatar_color,
        "about_status": user.about_status,
    }
