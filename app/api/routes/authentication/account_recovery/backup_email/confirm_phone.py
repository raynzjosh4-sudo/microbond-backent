import jwt
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import get_session
from app.models.user.user import User
from app.models.auth.otp import OTPRecord
from app.communications.sms_service import sanitize_uganda_phone
from app.api.dependencies import get_email_recovery_user
from app.api.routes.kyc.phone.fetch_and_save_kyc import fetch_and_save_kyc
from app.core.rate_limit import RateLimiter
from .schemas import ConfirmRecoveryPhoneOTPRequest, ConfirmRecoveryPhoneOTPResponse

router = APIRouter()


@router.post(
    "/recovery/email/confirm-phone",
    response_model=ConfirmRecoveryPhoneOTPResponse,
    summary="Confirm SMS OTP & Update Account Phone Number",
    description="Validates the SMS OTP sent to the new phone number, updates user.phone_number, and issues a final recovery token for setting a new PIN.",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))]
)
def confirm_recovery_phone(
    payload: ConfirmRecoveryPhoneOTPRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: User = Depends(get_email_recovery_user)
):
    try:
        new_phone = sanitize_uganda_phone(payload.new_phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Double check if someone claimed the number during the OTP window
    existing_user = session.exec(select(User).where(User.phone_number == new_phone)).first()
    if existing_user and existing_user.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New phone number is already registered to another account."
        )

    otp_statement = select(OTPRecord).where(
        OTPRecord.phone_number == new_phone,
        OTPRecord.code == payload.code.strip(),
        OTPRecord.is_used == False,
        OTPRecord.expires_at > datetime.now(timezone.utc)
    )
    otp_record = session.exec(otp_statement).first()

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired SMS OTP."
        )

    otp_record.is_used = True
    user.phone_number = new_phone
    user.is_phone_verified = True

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

    # Re-fetch telecom KYC records for the new phone number
    background_tasks.add_task(fetch_and_save_kyc, user.phone_number, user.id)

    # Issue final recovery token scoped for /pin/set
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode = {
        "sub": str(user.id),
        "phone": user.phone_number,
        "scope": "recovery",
        "exp": expire,
    }
    recovery_token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return ConfirmRecoveryPhoneOTPResponse(
        status="success",
        message="Phone number updated successfully. Please proceed to set a new PIN.",
        recovery_token=recovery_token
    )
