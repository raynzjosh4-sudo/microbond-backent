from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.kyc import KycProfile
from .schemas import UpdateUserNameRequest

router = APIRouter()


@router.patch("/me/name", summary="Update Current User Full Name")
def update_current_user_name(
    request: UpdateUserNameRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    clean_name = request.full_name.strip()
    if len(clean_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name must be at least 2 characters long.",
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
        kyc_profile.last_name = (
            " ".join(parts[1:]) if len(parts) > 1 else ""
        )
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
            "kyc_tier": db_user.kyc_tier,
        },
    }
