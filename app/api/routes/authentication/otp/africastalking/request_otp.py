import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError
from app.models.auth.otp import OTPRecord
from app.communications.sms_service import send_real_otp_sms, sanitize_uganda_phone
from app.core.database import get_session
from app.core.otp_security import OTP_TTL_SECONDS, generate_otp_code, hash_otp
from .schemas import OTPRequest, OTPRequestResponse

router = APIRouter()
from app.core.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

@router.post(
    "/request-otp",
    summary="Login / Register: Request OTP",
    description=(
        "Generates a 6-digit OTP and sends it via Africa's Talking SMS. "
        "Only a one-way hash is stored in the database."
    ),
    status_code=status.HTTP_200_OK,
    response_model=OTPRequestResponse,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
def request_otp(
    payload: OTPRequest,
    session: Session = Depends(get_session),
):
    try:
        phone = sanitize_uganda_phone(payload.phone_number)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(hours=24)
    recent_otps = session.exec(
        select(OTPRecord).where(
            OTPRecord.phone_number == phone,
            OTPRecord.created_at >= twenty_four_hours_ago,
        )
    ).all()

    if len(recent_otps) >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "You have reached the maximum limit of 3 free OTP requests per day. "
                "Please try again later."
            ),
        )

    if recent_otps:
        last_otp = max(recent_otps, key=lambda record: record.created_at)
        if last_otp.created_at > now - timedelta(minutes=1):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait at least 1 minute before requesting another OTP.",
            )

    otp_code = generate_otp_code()
    otp_hash = hash_otp(phone, otp_code)
    expiry = now + timedelta(seconds=OTP_TTL_SECONDS)

    try:
        existing_otps = session.exec(
            select(OTPRecord).where(
                OTPRecord.phone_number == phone,
                OTPRecord.is_used.is_(False),
            )
        ).all()

        for record in existing_otps:
            record.is_used = True
            session.add(record)

        new_otp = OTPRecord(
            phone_number=phone,
            code_hash=otp_hash,
            is_used=False,
            created_at=now,
            expires_at=expiry,
        )
        session.add(new_otp)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while preparing your OTP.",
        )

    try:
        sent = send_real_otp_sms(phone_number=phone, code=otp_code)
    except Exception:
        logger.exception("SMS provider failed while sending a login OTP.")
        sent = False

    if not sent:
        try:
            new_otp.is_used = True
            session.add(new_otp)
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("Could not invalidate OTP after SMS delivery failed.")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send SMS OTP. Please try again later.",
        )

    return OTPRequestResponse(
        status="success",
        message=f"A verification code was sent to {mask_phone(phone)}.",
        expires_in_seconds=OTP_TTL_SECONDS,
    )


def mask_phone(phone: str) -> str:
    if len(phone) <= 7:
        return "••••"
    return f"{phone[:4]}••••{phone[-3:]}"
