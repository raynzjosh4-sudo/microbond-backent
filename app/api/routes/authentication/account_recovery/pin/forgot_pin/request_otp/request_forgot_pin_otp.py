from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from app.core.database import get_session
from app.models.user.user import User
from app.models.auth.otp import OTPRecord
from app.communications.sms_service import send_real_otp_sms, sanitize_uganda_phone
from app.utils.codes import generate_6digit_code
from .schemas import RequestForgotPinOTPRequest, RequestForgotPinOTPResponse

router = APIRouter()

@router.post("/pin/forgot/request-otp", response_model=RequestForgotPinOTPResponse, summary="Request OTP to reset forgotten PIN", status_code=status.HTTP_200_OK)
def request_forgot_pin_otp(payload: RequestForgotPinOTPRequest, session: Session = Depends(get_session)):
    try:
        phone = sanitize_uganda_phone(payload.phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 1. Ensure user exists
    user_stmt = select(User).where(User.phone_number == phone)
    user = session.exec(user_stmt).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account with this phone number not found.")

    # 2. Rate limiting checks
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_otps_stmt = select(OTPRecord).where(
        OTPRecord.phone_number == phone,
        OTPRecord.created_at >= twenty_four_hours_ago
    )
    recent_otps = session.exec(recent_otps_stmt).all()
    
    if len(recent_otps) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have reached the maximum limit of OTP requests per day. Please contact support if you need more."
        )

    if recent_otps:
        last_otp = max(recent_otps, key=lambda r: r.created_at)
        if last_otp.created_at > datetime.now(timezone.utc) - timedelta(minutes=1):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait at least 1 minute before requesting another OTP."
            )

    # 3. Generate and invalidate old OTPs
    otp_code = generate_6digit_code()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

    try:
        existing_otps = session.exec(
            select(OTPRecord).where(OTPRecord.phone_number == phone, OTPRecord.is_used == False)
        ).all()
        for record in existing_otps:
            record.is_used = True
            session.add(record)
    
        new_otp = OTPRecord(phone_number=phone, code=otp_code, expires_at=expiry)
        session.add(new_otp)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while preparing your OTP."
        )

    # 4. Send the SMS
    try:
        sent = send_real_otp_sms(phone_number=phone, code=otp_code)
    except Exception:
        sent = False

    if not sent:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to send SMS OTP. Please try again later.")

    return RequestForgotPinOTPResponse(
        status="success",
        message=f"OTP sent to {phone} to reset your PIN.",
        expires_in_seconds=300
    )
