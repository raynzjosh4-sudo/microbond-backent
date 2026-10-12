from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional, List
from datetime import datetime, timezone
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
        "full_name": user.full_name,
        "profile_picture_url": user.profile_picture_url,
        "avatar_color": user.avatar_color,
        "about_status": user.about_status
    }

from app.api.dependencies import get_current_user
from app.models.user.security_email import UserSecurityEmail
from app.models.group.group import GroupMembership
from app.services.group.group_auth_service import evaluate_group_creation_permissions
from sqlalchemy import func

def mask_email_address(email: Optional[str]) -> Optional[str]:
    if not email or "@" not in email:
        return None
    user_part, domain = email.split("@", 1)
    if len(user_part) <= 2:
        masked_user = user_part[0] + "*"
    else:
        masked_user = user_part[:2] + "*" * (len(user_part) - 2)
    return f"{masked_user}@{domain}"

@router.get("/me", summary="Get Full Authenticated User Profile")
def get_current_user_profile(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the complete profile of the authenticated user:
    - Core credentials & verified status
    - Profile customization (name, avatar URL, avatar color, status bio)
    - Security state (has app PIN set, masked backup email, SIM-swap cooldown)
    - Financial & group stats (active groups count, referrals, trust score)
    """
    # 1. Fetch verified backup email
    sec_email_row = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.user_id == current_user.id,
            UserSecurityEmail.is_verified == True
        )
    ).first()

    # 2. Count active group memberships
    active_groups_count = session.exec(
        select(func.count()).where(
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).one()

    # 3. Derive reputation tier badge
    reputation_badge = "Newcomer"
    if current_user.trust_score >= 80:
        reputation_badge = "Elite Member"
    elif current_user.trust_score >= 50:
        reputation_badge = "Trusted Member"
    elif current_user.trust_score >= 20:
        reputation_badge = "Active Member"

    return {
        "status": "success",
        "data": {
            "user_id": str(current_user.id),
            "phone_number": current_user.phone_number,
            "full_name": current_user.full_name,
            "profile_picture_url": current_user.profile_picture_url,
            "avatar_color": current_user.avatar_color,
            "about_status": current_user.about_status,
            "is_phone_verified": current_user.is_phone_verified,
            "is_profile_complete": current_user.is_profile_complete,
            "kyc_tier": current_user.kyc_tier,
            "kyc_status": current_user.kyc_status,
            "trust_score": current_user.trust_score,
            "reputation_badge": reputation_badge,
            "has_app_pin": bool(current_user.hashed_pin is not None),
            "has_verified_backup_email": bool(sec_email_row is not None),
            "backup_email": mask_email_address(sec_email_row.email) if sec_email_row else None,
            "active_groups_count": active_groups_count,
            "referral_code": current_user.referral_code,
            "total_referrals": current_user.total_referrals,
            "total_earned": current_user.total_earned,
            "created_at": int(current_user.created_at.timestamp() * 1000) if current_user.created_at else None,
            "is_security_cooldown_active": bool(current_user.security_cooldown_until and current_user.security_cooldown_until > int(datetime.now(timezone.utc).timestamp() * 1000)) if hasattr(current_user, 'security_cooldown_until') else False
        }
    }

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

