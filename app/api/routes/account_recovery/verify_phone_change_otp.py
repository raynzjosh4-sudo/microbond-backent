from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import get_session
from app.models.user.user import User
from app.models.auth.otp import OTPRecord
from app.communications.sms_service import sanitize_uganda_phone

router = APIRouter()

class VerifyChangePhoneOTPRequest(BaseModel):
    current_phone_number: str
    new_phone_number: str
    code: str

class VerifyChangePhoneOTPResponse(BaseModel):
    status: str
    message: str

@router.post("/change-phone/confirm-and-update", response_model=VerifyChangePhoneOTPResponse, summary="Confirm OTP & Update Phone Number", status_code=status.HTTP_200_OK)
def verify_phone_change_otp(payload: VerifyChangePhoneOTPRequest, session: Session = Depends(get_session)):
    try:
        current_phone = sanitize_uganda_phone(payload.current_phone_number)
        new_phone = sanitize_uganda_phone(payload.new_phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        
    user = session.exec(select(User).where(User.phone_number == current_phone)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current user not found.")
        
    existing_user = session.exec(select(User).where(User.phone_number == new_phone)).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New phone number is already registered.")
        
    statement = select(OTPRecord).where(
        OTPRecord.phone_number == new_phone,
        OTPRecord.code == payload.code,
        OTPRecord.is_used == False,
        OTPRecord.expires_at > datetime.now(timezone.utc)
    )
    otp_record = session.exec(statement).first()
    
    if not otp_record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP.")
        
    otp_record.is_used = True
    user.phone_number = new_phone
    
    try:
        session.add(otp_record)
        session.add(user)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the phone number."
        )
        
    return VerifyChangePhoneOTPResponse(
        status="success",
        message="Phone number updated successfully."
    )
