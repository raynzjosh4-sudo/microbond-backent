import jwt
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import get_session
from app.models.user.user import User
from app.models.user.security_email import UserSecurityEmail
from app.core.rate_limit import RateLimiter
from .schemas import VerifyEmailRecoveryCodeRequest, VerifyEmailRecoveryCodeResponse

router = APIRouter()


@router.post(
    "/recovery/email/verify-code",
    response_model=VerifyEmailRecoveryCodeResponse,
    summary="Verify Backup Email Recovery Code",
    description="Validates the 6-digit code received via backup email. On success, issues a recovery token to update phone or reset PIN.",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))]
)
def verify_email_recovery_code(
    payload: VerifyEmailRecoveryCodeRequest,
    session: Session = Depends(get_session)
):
    normalized_email = payload.email.strip().lower()

    sec_email = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.email == normalized_email,
            UserSecurityEmail.is_verified == True
        )
    ).first()

    if not sec_email or not sec_email.verification_token or not sec_email.verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending recovery request found for this email. Please request a new code."
        )

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    if now_ms > sec_email.verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recovery code has expired. Please request a new code."
        )

    if sec_email.verification_token != payload.code.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid recovery code."
        )

    user = session.get(User, sec_email.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account associated with this email no longer exists."
        )

    # Invalidate token so it cannot be reused
    sec_email.verification_token = None
    sec_email.verification_expires_at = None

    try:
        session.add(sec_email)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while finalizing email verification."
        )

    # Issue recovery token with scope='recovery'
    # Compatible with /pin/set and recovery phone updates
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode = {
        "sub": str(user.id),
        "phone": user.phone_number,
        "scope": "recovery",
        "exp": expire,
    }
    recovery_token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return VerifyEmailRecoveryCodeResponse(
        status="success",
        message="Backup email verified successfully. You may now register a new phone number or proceed directly to set a new PIN.",
        temp_recovery_token=recovery_token
    )
