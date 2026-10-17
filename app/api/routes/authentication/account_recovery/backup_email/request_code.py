import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_session
from app.models.user.security_email import UserSecurityEmail
from app.services.communication.email_service import EmailNotificationService
from app.services.communication import email_templates
from app.core.rate_limit import RateLimiter
from .schemas import RequestEmailRecoveryCodeRequest, RequestEmailRecoveryCodeResponse

router = APIRouter()


@router.post(
    "/recovery/email/request-code",
    response_model=RequestEmailRecoveryCodeResponse,
    summary="Request Account Recovery Code via Backup Email",
    description="Sends a 6-digit one-time code to the user's verified backup email address to initiate account recovery.",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))]
)
def request_email_recovery_code(
    payload: RequestEmailRecoveryCodeRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    normalized_email = payload.email.strip().lower()

    sec_email = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.email == normalized_email,
            UserSecurityEmail.is_verified == True
        )
    ).first()

    if not sec_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account associated with this verified backup email was found."
        )

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    # Prevent flooding if an OTP was generated less than 60 seconds ago
    if sec_email.verification_expires_at:
        # 15 minutes window: expires_at - 14 minutes = 60s from creation
        time_since_creation_approx = (sec_email.verification_expires_at - (14 * 60 * 1000))
        if now_ms < time_since_creation_approx:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait at least 1 minute before requesting another recovery code."
            )

    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = now_ms + (15 * 60 * 1000)  # 15 minutes

    sec_email.verification_token = code
    sec_email.verification_expires_at = expires_at

    try:
        session.add(sec_email)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate recovery code due to a database error."
        )

    # Send recovery email via background task
    body = email_templates.otp_code(code, purpose="Account Recovery")
    background_tasks.add_task(
        EmailNotificationService.send_email,
        normalized_email,
        "Microbond: Your Account Recovery Code",
        body
    )

    return RequestEmailRecoveryCodeResponse(
        status="success",
        message=f"A 6-digit recovery code has been sent to {normalized_email}.",
        expires_in_seconds=900
    )
