from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from app.core.database import get_session
from app.models.user.user import User
from app.core.security import hash_pin, verify_pin
from app.api.dependencies import get_current_user
from app.core.rate_limit import RateLimiter
from .schemas import ChangeAppPinRequest, ChangeAppPinResponse

router = APIRouter()

@router.put(
    "/pin/change", 
    response_model=ChangeAppPinResponse, 
    summary="Change App PIN for an authenticated user", 
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))]
)
def change_app_pin(
    payload: ChangeAppPinRequest, 
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    # Verify the new PIN length
    if len(payload.new_pin) < 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New PIN must be at least 4 digits.")
        
    # Verify that the user already has a PIN
    if not user.hashed_pin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You do not have a PIN set yet. Please use the set PIN endpoint.")
        
    # Verify the old PIN
    if not verify_pin(payload.old_pin, user.hashed_pin):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="The old PIN is incorrect.")
        
    # Verify new PIN is not the same as old PIN
    if payload.old_pin == payload.new_pin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The new PIN cannot be the same as the old PIN.")

    # Hash and save the new PIN
    user.hashed_pin = hash_pin(payload.new_pin)
    
    try:
        session.add(user)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while changing the PIN."
        )
        
    return ChangeAppPinResponse(
        status="success", 
        message="App PIN has been changed successfully."
    )
