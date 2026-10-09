from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from pydantic import BaseModel
from app.core.database import get_session
from app.models.user.user import User
from app.models.auth.otp import OTPRecord
from app.communications.sms_service import send_real_otp_sms, sanitize_uganda_phone
from app.api.routes.at_otp_auth import generate_6digit_code
from app.core.security import verify_pin

router = APIRouter()

class RequestRecoveryOTPRequest(BaseModel):
    old_phone_number: str
    app_pin: str
    new_phone_number: str

class RequestRecoveryOTPResponse(BaseModel):
    status: str
    message: str
    expires_in_seconds: int

@router.post("/recovery/request-otp", response_model=RequestRecoveryOTPResponse, summary="Request OTP for account recovery using PIN", status_code=status.HTTP_200_OK)
def request_recovery_otp(payload: RequestRecoveryOTPRequest, session: Session = Depends(get_session)):
    try:
        old_phone = sanitize_uganda_phone(payload.old_phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    user_stmt = select(User).where(User.phone_number == old_phone)
    user = session.exec(user_stmt).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account with the old phone number not found.")

    if not user.hashed_pin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="App PIN was not set up for this account. Recovery unavailable.")

    if not verify_pin(payload.app_pin, user.hashed_pin):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect App PIN.")

    try:
        new_phone = sanitize_uganda_phone(payload.new_phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    existing_user_stmt = select(User).where(User.phone_number == new_phone)
    existing_user = session.exec(existing_user_stmt).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New phone number is already registered to another account.")

    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_otps_stmt = select(OTPRecord).where(
        OTPRecord.phone_number == new_phone,
        OTPRecord.created_at >= twenty_four_hours_ago
    )
    recent_otps = session.exec(recent_otps_stmt).all()
    
    if len(recent_otps) >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have reached the maximum limit of 3 free OTP requests per day. Please contact support if you need more."
        )

    if recent_otps:
        last_otp = max(recent_otps, key=lambda r: r.created_at)
        if last_otp.created_at > datetime.now(timezone.utc) - timedelta(minutes=1):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait at least 1 minute before requesting another OTP."
            )

    otp_code = generate_6digit_code()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

    try:
        existing_otps = session.exec(
            select(OTPRecord).where(OTPRecord.phone_number == new_phone, OTPRecord.is_used == False)
        ).all()
        for record in existing_otps:
            record.is_used = True
            session.add(record)
    
        new_otp = OTPRecord(phone_number=new_phone, code=otp_code, expires_at=expiry)
        session.add(new_otp)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while preparing your OTP."
        )

    try:
        sent = send_real_otp_sms(phone_number=new_phone, code=otp_code)
    except Exception:
        sent = False

    if not sent:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to send SMS OTP. Please try again later.")

    return RequestRecoveryOTPResponse(
        status="success",
        message=f"OTP sent to {new_phone}",
        expires_in_seconds=300
    )
