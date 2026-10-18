import time
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.kyc import KycProfile
from app.models.user.security_email import UserSecurityEmail
from app.models.user.userpaymentmethod.payment_method import UserPaymentMethod
from app.models.user.userpayoutaccount.payout_destination import (
    UserPayoutDestination,
)
from app.models.group.group import Group, GroupMembership

router = APIRouter()


@router.get("/me/export-gdpr", summary="GDPR: Export Complete Personal Data Archive")
def export_user_data(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    kyc_row = session.exec(
        select(KycProfile).where(KycProfile.user_id == current_user.id)
    ).first()
    kyc_data = None
    if kyc_row:
        kyc_data = {
            "first_name": kyc_row.first_name,
            "last_name": kyc_row.last_name,
            "dob": kyc_row.dob,
            "gender": kyc_row.gender,
            "document_type": kyc_row.document_type,
            "nin_masked": (
                kyc_row.id_number[:4] + "****" + kyc_row.id_number[-2:]
                if kyc_row.id_number and len(kyc_row.id_number) >= 6
                else None
            ),
            "sim_registered_name": kyc_row.sim_registered_name,
            "sim_carrier": kyc_row.sim_carrier,
            "kyc_status": kyc_row.kyc_status,
            "verified_at": kyc_row.verified_at,
        }

    sec_email = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.user_id == current_user.id
        )
    ).first()
    payout_methods = session.exec(
        select(UserPayoutDestination).where(
            UserPayoutDestination.user_id == current_user.id
        )
    ).all()
    payment_methods = session.exec(
        select(UserPaymentMethod).where(
            UserPaymentMethod.user_id == current_user.id
        )
    ).all()

    memberships = session.exec(
        select(GroupMembership).where(
            GroupMembership.user_id == current_user.id
        )
    ).all()
    group_ids = [m.group_id for m in memberships]
    groups = (
        session.exec(select(Group).where(Group.group_id.in_(group_ids))).all()
        if group_ids
        else []
    )
    group_dict = {g.group_id: g.name for g in groups}

    group_history = [
        {
            "group_id": m.group_id,
            "group_name": group_dict.get(m.group_id, "Unknown"),
            "role": m.role,
            "status": m.status,
            "total_contributed": m.total_contributed,
            "joined_at": m.joined_at,
            "left_at": m.left_at,
        }
        for m in memberships
    ]

    return {
        "status": "success",
        "exported_at": int(time.time() * 1000),
        "data": {
            "user_id": str(current_user.id),
            "phone_number": current_user.phone_number,
            "full_name": current_user.full_name,
            "profile_picture_url": current_user.profile_picture_url,
            "avatar_color": current_user.avatar_color,
            "about_status": current_user.about_status,
            "privacy_settings": {
                "profile_photo_visibility": getattr(current_user, "profile_photo_visibility", "EVERYONE"),
                "about_visibility": getattr(current_user, "about_visibility", "EVERYONE"),
                "group_add_permission": getattr(current_user, "group_add_permission", "EVERYONE"),
            },
            "kyc_tier": current_user.kyc_tier,
            "trust_score": current_user.trust_score,
            "created_at": (
                current_user.created_at.isoformat()
                if current_user.created_at
                else None
            ),
            "security_email": (
                sec_email.email
                if (sec_email and sec_email.is_verified)
                else None
            ),
            "identity_verification": kyc_data,
            "registered_payout_destinations": [
                {
                    "network": p.network,
                    "phone_number": (
                        p.phone_number[:6] + "****" + p.phone_number[-2:]
                        if len(p.phone_number) >= 8
                        else p.phone_number
                    ),
                    "account_holder_name": p.account_holder_name,
                    "is_verified": p.is_verified,
                }
                for p in payout_methods
            ],
            "registered_payment_methods": [
                {
                    "network": m.network,
                    "phone_number": (
                        m.phone_number[:6] + "****" + m.phone_number[-2:]
                        if len(m.phone_number) >= 8
                        else m.phone_number
                    ),
                    "is_auto_pay_enabled": m.is_auto_pay_enabled,
                }
                for m in payment_methods
            ],
            "group_participations": group_history,
        },
    }
