from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from pydantic import BaseModel
from app.core.database import get_session
from app.models.user.user import User
from app.core.security import hash_pin, create_access_token
from app.communications.sms_service import sanitize_uganda_phone
from app.api.dependencies import get_pin_setup_user

router = APIRouter()

class SetAppPinRequest(BaseModel):
    pin: str

class SetAppPinResponse(BaseModel):
    status: str
    message: str
    access_token: str
    token_type: str = "bearer"

@router.post("/pin/set", response_model=SetAppPinResponse, summary="Set App PIN for the user", status_code=status.HTTP_200_OK)
def set_app_pin(
    payload: SetAppPinRequest, 
    session: Session = Depends(get_session),
    user: User = Depends(get_pin_setup_user)
):
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
        
    # Generate full access token since they successfully authenticated and reset PIN
    access_token = create_access_token(data={"sub": str(user.id), "phone": user.phone_number})
    
    return SetAppPinResponse(
        status="success", 
        message="App PIN has been set successfully.",
        access_token=access_token
    )
