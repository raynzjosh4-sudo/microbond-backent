import jwt
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from pydantic import BaseModel
from app.core.config import settings
from app.core.database import get_session
from app.models.user.user import User
from app.models.auth.otp import OTPRecord
from app.communications.sms_service import sanitize_uganda_phone

router = APIRouter()

class VerifyForgotPinOTPRequest(BaseModel):
    phone_number: str
    code: str

class VerifyForgotPinOTPResponse(BaseModel):
    status: str
    message: str
    recovery_token: str
    token_type: str = "bearer"

from app.core.rate_limit import RateLimiter

@router.post(
    "/pin/forgot/verify-otp", 
    response_model=VerifyForgotPinOTPResponse, 
    summary="Verify OTP to reset forgotten PIN", 
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))]
)
def verify_forgot_pin_otp(payload: VerifyForgotPinOTPRequest, session: Session = Depends(get_session)):
    try:
        phone = sanitize_uganda_phone(payload.phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 1. Fetch user
    user = session.exec(select(User).where(User.phone_number == phone)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    # 2. Check the most recent OTP
    otp_record = session.exec(
        select(OTPRecord)
        .where(OTPRecord.phone_number == phone, OTPRecord.is_used == False)
        .order_by(OTPRecord.created_at.desc())
    ).first()

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP found for this number. Please request a new one."
        )

    if otp_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new one."
        )

    if otp_record.code != payload.code:
        otp_record.attempts += 1
        if otp_record.attempts >= 3:
            otp_record.is_used = True
            session.add(otp_record)
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many invalid attempts. OTP invalidated. Request a new one."
            )
        session.add(otp_record)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid OTP code. You have {3 - otp_record.attempts} attempts remaining."
        )

    # 3. Mark OTP as used
    otp_record.is_used = True
    session.add(otp_record)
    
    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete OTP verification."
        )

    # 4. Generate recovery token with scope='recovery'
    # This token will allow them to hit the /pin/set endpoint via get_pin_setup_user dependency
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode = {
        "sub": str(user.id),
        "phone": user.phone_number,
        "scope": "recovery",
        "exp": expire
    }
    recovery_token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return VerifyForgotPinOTPResponse(
        status="success",
        message="OTP verified successfully. Please proceed to set a new PIN.",
        recovery_token=recovery_token
    )
