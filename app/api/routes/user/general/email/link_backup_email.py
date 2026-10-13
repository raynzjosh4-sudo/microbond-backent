import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.security_email import UserSecurityEmail
from app.services.communication.email_service import EmailNotificationService
from app.services.communication import email_templates
from .schemas import LinkEmailRequest
from .helpers.mask_phone_number import mask_phone_number

router = APIRouter()


@router.post(
    "/link",
    summary="Link Secondary Backup Email",
    description="Registers a backup email address in the dedicated UserSecurityEmail table and sends a 6-digit verification code. If the email is already linked to another account, a security alert is dispatched.",
)
async def link_backup_email(
    payload: LinkEmailRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = int(datetime.now(timezone.utc).timestamp() * 1000) + (
        15 * 60 * 1000
    )  # 15 mins

    # Check if this email is already linked and verified to another account
    existing_other_verified = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.email == payload.email,
            UserSecurityEmail.user_id != current_user.id,
            UserSecurityEmail.is_verified == True,
        )
    ).first()

    sec_email = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.user_id == current_user.id
        )
    ).first()

    if not sec_email:
        sec_email = UserSecurityEmail(
            user_id=current_user.id,
            email=payload.email,
            is_verified=False,
            verification_token=code,
            verification_expires_at=expires_at,
        )
    else:
        sec_email.email = payload.email
        sec_email.is_verified = False
        sec_email.verification_token = code
        sec_email.verification_expires_at = expires_at

    session.add(sec_email)
    session.commit()

    masked_phone = mask_phone_number(current_user.phone_number)

    if existing_other_verified:
        # Alert the inbox that another account is attempting to link this email
        background_tasks.add_task(
            EmailNotificationService.send_security_alert_email_takeover_attempt,
            payload.email,
            code,
            masked_phone,
        )
        return {
            "status": "success",
            "message": f"Verification code sent to {payload.email}. Since this email was previously verified on another account, confirming will transfer it and disconnect the old account.",
        }
    else:
        # Dispatch standard verification code email
        body = email_templates.verification_code(code, payload.email)
        background_tasks.add_task(
            EmailNotificationService.send_email,
            payload.email,
            "Microbond: Verify Your Backup Email",
            body,
        )
        return {
            "status": "success",
            "message": f"Verification code sent to {payload.email}",
        }
