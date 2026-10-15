from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.user.userpaymentmethod.payment_method import UserPaymentMethod
from .schemas import GroupPaymentMethodResponse
from .helpers import mask_account_number

router = APIRouter()

@router.get("/{group_id}/membership/me/payment-method", response_model=GroupPaymentMethodResponse, summary="Get group contribution payment method")
def get_group_payment_method(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="You are not a member of this group.")

    # 1. Try group-specific payment method
    if membership.payment_method_id:
        pm = session.query(UserPaymentMethod).filter_by(id=membership.payment_method_id).first()
        if pm:
            return GroupPaymentMethodResponse(
                payment_method_id=pm.id,
                provider_name=pm.provider_name,
                account_number=pm.account_number,
                account_name=pm.verified_name or "Unknown",
                verified_name=pm.verified_name,
                is_verified=pm.is_verified,
                verification_type=pm.verification_type,
                masked_number=mask_account_number(pm.account_number),
                is_fallback=False
            )

    # 2. Try global default payment method
    default_pm = session.query(UserPaymentMethod).filter_by(user_id=current_user.id, is_default=True).first()
    if default_pm:
        return GroupPaymentMethodResponse(
            payment_method_id=default_pm.id,
            provider_name=default_pm.provider_name,
            account_number=default_pm.account_number,
            account_name=default_pm.verified_name or "Unknown",
            verified_name=default_pm.verified_name,
            is_verified=default_pm.is_verified,
            verification_type=default_pm.verification_type,
            masked_number=mask_account_number(default_pm.account_number),
            is_fallback=True
        )

    # 3. Ultimate Fallback: The user's registered phone number
    return GroupPaymentMethodResponse(
        payment_method_id=None,
        provider_name="Mobile Money (Registered Number)",
        account_number=current_user.phone_number,
        account_name=current_user.full_name or "Unknown",
        verified_name=current_user.full_name,
        is_verified=True,
        verification_type="FALLBACK",
        masked_number=mask_account_number(current_user.phone_number),
        is_fallback=True
    )
