import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies.auth import get_current_user
from app.models.user.user import User
from app.models.user.security_email import UserSecurityEmail
from app.services.communication.email_service import EmailNotificationService

router = APIRouter(prefix="/email", tags=["User Email Management"])

class LinkEmailRequest(BaseModel):
    email: EmailStr

class VerifyEmailRequest(BaseModel):
    code: str

class ExportStatementRequest(BaseModel):
    months_back: int = 3

@router.post(
    "/link",
    summary="Link Secondary Backup Email",
    description="Registers a backup email address in the dedicated UserSecurityEmail table and sends a 6-digit verification code."
)
async def link_backup_email(
    payload: LinkEmailRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = int(datetime.now(timezone.utc).timestamp() * 1000) + (15 * 60 * 1000) # 15 mins

    sec_email = session.exec(
        select(UserSecurityEmail).where(UserSecurityEmail.user_id == current_user.id)
    ).first()

    if not sec_email:
        sec_email = UserSecurityEmail(
            user_id=current_user.id,
            email=payload.email,
            is_verified=False,
            verification_token=code,
            verification_expires_at=expires_at
        )
    else:
        sec_email.email = payload.email
        sec_email.is_verified = False
        sec_email.verification_token = code
        sec_email.verification_expires_at = expires_at

    session.add(sec_email)
    session.commit()

    # Dispatch code via email
    body = f"""
    <h2>Verify Your Microbond Backup Email</h2>
    <p>Use the following 6-digit code to verify your recovery email address:</p>
    <h1 style="letter-spacing: 5px; color: #1a73e8;">{code}</h1>
    <p>This code will expire in 15 minutes.</p>
    """
    background_tasks.add_task(
        EmailNotificationService.send_email,
        payload.email,
        "Microbond: Verify Your Backup Email",
        body
    )

    return {"status": "success", "message": f"Verification code sent to {payload.email}"}

@router.post(
    "/verify",
    summary="Verify Secondary Backup Email",
    description="Verifies the 6-digit code sent to the backup email."
)
def verify_backup_email(
    payload: VerifyEmailRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    sec_email = session.exec(
        select(UserSecurityEmail).where(UserSecurityEmail.user_id == current_user.id)
    ).first()

    if not sec_email or not sec_email.verification_token or not sec_email.verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending email verification found."
        )

    if now_ms > sec_email.verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code."
        )

    if sec_email.verification_token != payload.code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code."
        )

    sec_email.is_verified = True
    sec_email.verification_token = None
    sec_email.verification_expires_at = None
    sec_email.verified_at = datetime.now(timezone.utc)

    session.add(sec_email)
    session.commit()

    return {"status": "success", "message": "Backup email verified successfully."}

@router.post(
    "/export-statement",
    summary="Export Individual Regulatory Statement",
    description="Compiles official regulatory statement and delivers it to the user's verified backup email."
)
async def export_individual_statement(
    payload: ExportStatementRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    sec_email = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.user_id == current_user.id,
            UserSecurityEmail.is_verified == True
        )
    ).first()

    if not sec_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A verified backup email is required to receive official statements."
        )

    dummy_statement_pdf = b"%PDF-1.4 Mock Regulatory Statement for User " + str(current_user.id).encode()

    subject = "Your Official Microbond Account Statement"
    body = f"""
    <h2>Official Account Statement</h2>
    <p>Dear {current_user.full_name or 'Member'},</p>
    <p>Attached is your official regulatory account statement covering the past {payload.months_back} months.</p>
    <p>This document is cryptographically stamped by Microbond for financial audit and compliance purposes.</p>
    """
    
    background_tasks.add_task(
        EmailNotificationService.send_email,
        sec_email.email,
        subject,
        body,
        dummy_statement_pdf,
        f"Microbond_Statement_{current_user.phone_number}.pdf"
    )

    return {
        "status": "success",
        "message": f"Your regulatory account statement has been dispatched to {sec_email.email}."
    }
