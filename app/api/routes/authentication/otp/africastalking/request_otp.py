from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError
from app.models.auth.otp import OTPRecord
from app.communications.sms_service import send_real_otp_sms, sanitize_uganda_phone
from app.core.database import get_session
from app.utils.codes import generate_6digit_code
from .schemas import OTPRequest, OTPRequestResponse

router = APIRouter()

from fastapi_limiter.depends import RateLimiter

@router.post(
    "/request-otp",
    summary="Login / Register: Request OTP",
    description="Generates a 6-digit OTP and sends it via Africa's Talking SMS. Invalidates any previous unverified OTPs. Max 3 free requests per 24 hours.",
    status_code=status.HTTP_200_OK,
    response_model=OTPRequestResponse,
    # dependencies=[Depends(RateLimiter(times=5, seconds=60))] # Temporarily disabled: Requires Redis
)
def request_otp(payload: OTPRequest, session: Session = Depends(get_session)):
    # 1. Handle phone validation errors
    try:
        phone = sanitize_uganda_phone(payload.phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 2. Rate Limiting: Max 3 OTPs per 24 hours per phone number
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_otps_stmt = select(OTPRecord).where(
        OTPRecord.phone_number == phone, OTPRecord.created_at >= twenty_four_hours_ago
    )
    recent_otps = session.exec(recent_otps_stmt).all()

    if len(recent_otps) >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have reached the maximum limit of 3 free OTP requests per day. Please contact support if you need more.",
        )

    # 3. Cooldown check: Prevent requesting if an OTP was sent in the last 1 minute
    if recent_otps:
        last_otp = max(recent_otps, key=lambda r: r.created_at)
        # Ensure we're comparing offset-aware datetimes
        if last_otp.created_at > datetime.now(timezone.utc) - timedelta(minutes=1):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait at least 1 minute before requesting another OTP.",
            )

    otp_code = generate_6digit_code()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

    try:
        # Invalidate older unverified codes for this phone number
        existing_otps = session.exec(
            select(OTPRecord).where(
                OTPRecord.phone_number == phone, OTPRecord.is_used == False
            )
        ).all()

        for record in existing_otps:
            record.is_used = True
            session.add(record)

        # Save new OTP to database
        new_otp = OTPRecord(phone_number=phone, code=otp_code, expires_at=expiry)
        session.add(new_otp)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while preparing your OTP.",
        )

    # 4. Send SMS via Africa's Talking with failure handling
    try:
        sent = send_real_otp_sms(phone_number=phone, code=otp_code)
    except Exception:
        sent = False

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send SMS OTP. Please try again later.",
        )

    return OTPRequestResponse(
        status="success", message=f"OTP sent to {phone}", expires_in_seconds=300
    )
