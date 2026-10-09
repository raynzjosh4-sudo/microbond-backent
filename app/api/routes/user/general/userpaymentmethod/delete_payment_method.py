from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.userpaymentmethod.payment_method import UserPaymentMethod

router = APIRouter()

@router.delete("/{payment_method_id}", summary="Delete a payment method")
def delete_payment_method(
    payment_method_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    pm = session.query(UserPaymentMethod).filter_by(id=payment_method_id, user_id=current_user.id).first()
    
    if not pm:
        raise HTTPException(status_code=404, detail="Payment method not found")
        
    session.delete(pm)
    session.commit()
    
    return {"status": "success", "message": "Payment method deleted successfully"}
