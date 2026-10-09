from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.models.user.user import User
from app.core.database import get_session

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

@router.get("/{phone_number}/status", summary="Get User Profile Status")
def get_user_status(phone_number: str, session: Session = Depends(get_session)):
    """
    Fetch the user's current profile status.
    This is useful for when the app restarts and needs to check if KYC is completed.
    """
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number.strip()

    statement = select(User).where(User.phone_number == phone_number)
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    return {
        "status": "success",
        "user_id": user.id,
        "phone_number": user.phone_number,
        "is_phone_verified": user.is_phone_verified,
        "is_profile_complete": user.is_profile_complete,
        "kyc_tier": user.kyc_tier,
        "full_name": user.full_name
    }
