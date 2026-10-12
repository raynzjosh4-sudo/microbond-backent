from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.core.security import verify_pin
from app.models.user.userpaymentmethod.payment_method import UserPaymentMethod
from app.models.user.userpaymentmethod.schema.payment_method_schema import CreatePaymentMethodRequest, PaymentMethodResponse
from app.services.finance.payout_verification_service import PayoutAccountVerificationService

router = APIRouter()

def mask_account_number(number: str) -> str:
    if len(number) < 4:
        return "****"
    return f"**** {number[-4:]}"

@router.post("/", response_model=PaymentMethodResponse, summary="Add a new payment method")
async def add_payment_method(
    request: CreatePaymentMethodRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Step-Up PIN validation if user has an active PIN
    if current_user.hashed_pin:
        pin_to_check = request.app_pin if request.app_pin and request.app_pin.strip().lower() != "string" else None
        if not pin_to_check:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="App PIN is required to add a payment method. Please enter your valid 4-digit PIN."
            )
        if not verify_pin(pin_to_check, current_user.hashed_pin):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect App PIN."
            )

    # Auto-detect account_type ('MOBILE_MONEY' or 'BANK_ACCOUNT') if omitted
    resolved_type = PayoutAccountVerificationService.resolve_account_type(
        provider_name=request.provider_name,
        account_number=request.account_number,
        account_type=request.account_type
    )

    # Verify payment method using external authority (MTN / Airtel / Prembly)
    verification = await PayoutAccountVerificationService.verify(
        provider_name=request.provider_name,
        account_type=resolved_type,
        account_number=request.account_number,
        bank_code=None,
    )

    # If this is the user's first payment method, or they requested it, set as default
    existing = session.query(UserPaymentMethod).filter_by(user_id=current_user.id).all()
    is_default = request.is_default or len(existing) == 0

    if is_default:
        for pm in existing:
            pm.is_default = False
            session.add(pm)

    new_pm = UserPaymentMethod(
        user_id=current_user.id,
        provider_name=request.provider_name,
        account_number=request.account_number,
        account_name=verification.verified_name,
        account_type=resolved_type,
        is_verified=verification.is_verified,
        verified_name=verification.verified_name,
        verification_type=verification.verification_type,
        is_default=is_default
    )
    
    session.add(new_pm)
    session.commit()
    session.refresh(new_pm)

    return PaymentMethodResponse(
        id=new_pm.id,
        provider_name=new_pm.provider_name,
        account_number=new_pm.account_number,
        account_name=new_pm.account_name or new_pm.verified_name,
        account_type=new_pm.account_type,
        verified_name=new_pm.verified_name,
        is_verified=new_pm.is_verified,
        is_default=new_pm.is_default,
        masked_number=mask_account_number(new_pm.account_number),
        verification_type=new_pm.verification_type
    )
