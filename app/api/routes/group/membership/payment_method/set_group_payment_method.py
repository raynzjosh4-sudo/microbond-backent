from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.user.userpaymentmethod.payment_method import UserPaymentMethod
from .schemas import GroupPaymentMethodResponse, UpdateGroupPaymentMethodRequest
from .get_group_payment_method import get_group_payment_method

router = APIRouter()

@router.patch("/{group_id}/membership/me/payment-method", response_model=GroupPaymentMethodResponse, summary="Set group contribution payment method")
def set_group_payment_method(
    group_id: str,
    request: UpdateGroupPaymentMethodRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="You are not a member of this group.")

    if request.payment_method_id:
        # Verify the user actually owns this payment method
        pm = session.query(UserPaymentMethod).filter_by(
            id=request.payment_method_id, 
            user_id=current_user.id
        ).first()
        
        if not pm:
            raise HTTPException(status_code=404, detail="Payment method not found.")
            
        membership.payment_method_id = request.payment_method_id
    else:
        membership.payment_method_id = None
        
    session.commit()
    return get_group_payment_method(group_id, session, current_user)
