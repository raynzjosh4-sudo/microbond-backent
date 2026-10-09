from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from pydantic import BaseModel
from app.core.database import get_session
from app.models.user.user import User
from app.core.security import hash_pin
from app.communications.sms_service import sanitize_uganda_phone

router = APIRouter()

class SetAppPinRequest(BaseModel):
    phone_number: str
    pin: str

class SetAppPinResponse(BaseModel):
    status: str
    message: str

@router.post("/pin/set", response_model=SetAppPinResponse, summary="Set App PIN for the user", status_code=status.HTTP_200_OK)
def set_app_pin(payload: SetAppPinRequest, session: Session = Depends(get_session)):
    try:
        phone = sanitize_uganda_phone(payload.phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        
    statement = select(User).where(User.phone_number == phone)
    user = session.exec(statement).first()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        
    if len(payload.pin) < 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PIN must be at least 4 digits.")
        
    user.hashed_pin = hash_pin(payload.pin)
    
    try:
        session.add(user)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while setting the PIN."
        )
    
    return SetAppPinResponse(status="success", message="App PIN has been set successfully.")
