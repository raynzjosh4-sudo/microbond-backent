from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.userpaymentmethod.payment_method import UserPaymentMethod
from app.models.user.userpaymentmethod.schema.payment_method_schema import CreatePaymentMethodRequest, PaymentMethodResponse

router = APIRouter()

def mask_account_number(number: str) -> str:
    if len(number) < 4:
        return "****"
    return f"**** {number[-4:]}"

@router.post("/", response_model=PaymentMethodResponse, summary="Add a new payment method")
def add_payment_method(
    request: CreatePaymentMethodRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
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
        account_name=request.account_name,
        is_default=is_default
    )
    
    session.add(new_pm)
    session.commit()
    session.refresh(new_pm)

    return PaymentMethodResponse(
        id=new_pm.id,
        provider_name=new_pm.provider_name,
        account_number=new_pm.account_number,
        account_name=new_pm.account_name,
        is_default=new_pm.is_default,
        masked_number=mask_account_number(new_pm.account_number)
    )
