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

class VerifyRecoveryOTPRequest(BaseModel):
    phone_number: str
    code: str

class VerifyRecoveryOTPResponse(BaseModel):
    status: str
    message: str
    temp_recovery_token: str

@router.post("/recovery/verify-otp", response_model=VerifyRecoveryOTPResponse, summary="Verify OTP for account recovery", status_code=status.HTTP_200_OK)
def verify_recovery_otp(payload: VerifyRecoveryOTPRequest, session: Session = Depends(get_session)):
    try:
        phone = sanitize_uganda_phone(payload.phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        
    user = session.exec(select(User).where(User.phone_number == phone)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        
    statement = select(OTPRecord).where(
        OTPRecord.phone_number == phone,
        OTPRecord.code == payload.code,
        OTPRecord.is_used == False,
        OTPRecord.expires_at > datetime.now(timezone.utc)
    )
    otp_record = session.exec(statement).first()
    
    if not otp_record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP.")
        
    otp_record.is_used = True
    
    try:
        session.add(otp_record)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while verifying the OTP. Please try again."
        )
        
    temp_token = f"temp_rec_token_{user.id}"
    
    return VerifyRecoveryOTPResponse(
        status="success",
        message="OTP verified successfully. Please proceed to set a new PIN.",
        temp_recovery_token=temp_token
    )
