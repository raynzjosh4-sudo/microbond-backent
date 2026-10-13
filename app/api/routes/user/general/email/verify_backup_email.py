from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.security_email import UserSecurityEmail
from app.services.communication.email_service import EmailNotificationService
from .schemas import VerifyEmailRequest
from .helpers.mask_phone_number import mask_phone_number

router = APIRouter()


@router.post(
    "/verify",
    summary="Verify Secondary Backup Email",
    description="Verifies the 6-digit code sent to the backup email. If this email was previously linked to another account, it is safely disconnected.",
)
def verify_backup_email(
    payload: VerifyEmailRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    sec_email = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.user_id == current_user.id
        )
    ).first()

    if (
        not sec_email
        or not sec_email.verification_token
        or not sec_email.verification_expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending email verification found.",
        )

    if now_ms > sec_email.verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code.",
        )

    if sec_email.verification_token != payload.code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code.",
        )

    # Disconnect any other accounts that previously had this email linked
    other_accounts = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.email == sec_email.email,
            UserSecurityEmail.user_id != current_user.id,
        )
    ).all()

    had_prior_owner = len(other_accounts) > 0
    for old_account in other_accounts:
        session.delete(old_account)

    sec_email.is_verified = True
    sec_email.verification_token = None
    sec_email.verification_expires_at = None
    sec_email.verified_at = datetime.now(timezone.utc)

    session.add(sec_email)
    session.commit()

    # If this email was transferred from a prior account, send confirmation notification
    if had_prior_owner:
        masked_phone = mask_phone_number(current_user.phone_number)
        background_tasks.add_task(
            EmailNotificationService.send_security_email_unlinked_notification,
            sec_email.email,
            masked_phone,
        )

    return {
        "status": "success",
        "message": "Backup email verified successfully.",
    }
