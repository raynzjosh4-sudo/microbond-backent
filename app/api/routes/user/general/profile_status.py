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
    # Normalize phone numbers (e.g. 0704903741 -> +256704903741)
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
        (User.phone_number == normalized_phone) | (User.phone_number == alt_phone)
    )
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

from app.api.dependencies import get_current_user
from app.services.group.group_auth_service import evaluate_group_creation_permissions
from typing import List

@router.get("/me/allowed-groups", summary="Get Authorized Group Creation Types")
def get_allowed_groups(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Returns the group types the current user is allowed to create, 
    including the reasons for each unlocked or locked group type
    based on KYC tier, trust score, and historical group health.
    """
    evaluation = evaluate_group_creation_permissions(session, current_user.id)
    return {
        "status": "success",
        "allowed_groups": evaluation["allowed_groups"],
        "reasons": evaluation["reasons"],
        "allowed_group_details": evaluation["allowed_group_details"],
        "groups": evaluation["all_groups"]
    }

