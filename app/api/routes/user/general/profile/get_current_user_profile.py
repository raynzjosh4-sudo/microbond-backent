from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from sqlalchemy import func
from app.models.user.user import User
from app.models.user.security_email import UserSecurityEmail
from app.models.group.group import GroupMembership
from app.core.database import get_session
from app.api.dependencies import get_current_user
from .helpers.mask_email_address import mask_email_address

router = APIRouter()


@router.get("/me", summary="Get Full Authenticated User Profile")
def get_current_user_profile(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # 1. Fetch verified backup email
    sec_email_row = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.user_id == current_user.id,
            UserSecurityEmail.is_verified == True,
        )
    ).first()

    # 2. Count active group memberships
    active_groups_count = session.exec(
        select(func.count()).where(
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE",
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
            "backup_email": (
                mask_email_address(sec_email_row.email)
                if sec_email_row
                else None
            ),
            "active_groups_count": active_groups_count,
            "referral_code": current_user.referral_code,
            "total_referrals": current_user.total_referrals,
            "total_earned": current_user.total_earned,
            "created_at": (
                int(current_user.created_at.timestamp() * 1000)
                if current_user.created_at
                else None
            ),
            "is_security_cooldown_active": (
                bool(
                    current_user.security_cooldown_until
                    and current_user.security_cooldown_until
                    > int(datetime.now(timezone.utc).timestamp() * 1000)
                )
                if hasattr(current_user, "security_cooldown_until")
                else False
            ),
            "privacy_settings": {
                "profile_photo_visibility": getattr(current_user, "profile_photo_visibility", "EVERYONE"),
                "about_visibility": getattr(current_user, "about_visibility", "EVERYONE"),
                "group_add_permission": getattr(current_user, "group_add_permission", "EVERYONE"),
            },
        },
    }
