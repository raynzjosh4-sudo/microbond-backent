from fastapi import APIRouter, Depends
from sqlmodel import Session
from typing import List
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.userpaymentmethod.payment_method import UserPaymentMethod
from app.models.user.userpaymentmethod.schema.payment_method_schema import PaymentMethodResponse

router = APIRouter()

def mask_account_number(number: str) -> str:
    if len(number) < 4:
        return "****"
    return f"**** {number[-4:]}"

@router.get("/", response_model=List[PaymentMethodResponse], summary="List my payment methods")
def list_my_payment_methods(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    methods = session.query(UserPaymentMethod).filter_by(user_id=current_user.id).all()
    
    return [
        PaymentMethodResponse(
            id=pm.id,
            provider_name=pm.provider_name,
            account_number=pm.account_number,
            account_name=pm.account_name,
            is_default=pm.is_default,
            masked_number=mask_account_number(pm.account_number)
        )
        for pm in methods
    ]
