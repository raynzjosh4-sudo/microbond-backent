from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_session
from app.models.user.user import User
from app.models.auth.otp import OTPRecord
from app.communications.sms_service import send_real_otp_sms, sanitize_uganda_phone
from app.utils.codes.generate_6digit_code import generate_6digit_code
from app.api.dependencies import get_email_recovery_user
from app.core.rate_limit import RateLimiter
from .schemas import RequestRecoveryPhoneOTPRequest, RequestRecoveryPhoneOTPResponse

router = APIRouter()


@router.post(
    "/recovery/email/request-phone-otp",
    response_model=RequestRecoveryPhoneOTPResponse,
    summary="Request SMS OTP for New Phone during Email Recovery",
    description="Dispatches an SMS OTP to verify ownership of the new phone number before updating the account.",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))]
)
def request_recovery_phone_otp(
    payload: RequestRecoveryPhoneOTPRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_email_recovery_user)
):
    try:
        new_phone = sanitize_uganda_phone(payload.new_phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Verify that the new phone is not already in use by another user
    existing_user = session.exec(select(User).where(User.phone_number == new_phone)).first()
    if existing_user and existing_user.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New phone number is already registered to another account."
        )

    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_otps = session.exec(
        select(OTPRecord).where(
            OTPRecord.phone_number == new_phone,
            OTPRecord.created_at >= twenty_four_hours_ago
        )
    ).all()

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
        existing_unused = session.exec(
            select(OTPRecord).where(
                OTPRecord.phone_number == new_phone,
                OTPRecord.is_used == False
            )
        ).all()
        for record in existing_unused:
            record.is_used = True
            session.add(record)

        new_otp = OTPRecord(phone_number=new_phone, code=otp_code, expires_at=expiry)
        session.add(new_otp)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while preparing SMS OTP."
        )

    try:
        sent = send_real_otp_sms(phone_number=new_phone, code=otp_code)
    except Exception:
        sent = False

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send SMS OTP. Please check the phone number or try again later."
        )

    return RequestRecoveryPhoneOTPResponse(
        status="success",
        message=f"SMS OTP sent to {new_phone}.",
        expires_in_seconds=300
    )
