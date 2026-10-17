from fastapi import APIRouter, Depends, status
from sqlmodel import Session, select
from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.models.user.security_email import UserSecurityEmail
from app.models.user.user import User
from .schemas import GetBackupEmailResponse, BackupEmailData

router = APIRouter()


@router.get(
    "/backup",
    response_model=GetBackupEmailResponse,
    summary="Get Authenticated User Backup/Recovery Email",
    description="Returns the secondary backup email address, verification status, and timestamps for the logged-in user.",
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/recovery-email",
    response_model=GetBackupEmailResponse,
    summary="Get Authenticated User Backup/Recovery Email (Alias)",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_backup_email(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    sec_email = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.user_id == current_user.id
        )
    ).first()

    if not sec_email:
        return GetBackupEmailResponse(
            status="success",
            has_backup_email=False,
            data=None,
        )

    data = BackupEmailData(
        email=sec_email.email,
        is_verified=sec_email.is_verified,
        created_at=(
            int(sec_email.created_at.timestamp() * 1000)
            if sec_email.created_at
            else None
        ),
        verified_at=(
            int(sec_email.verified_at.timestamp() * 1000)
            if sec_email.verified_at
            else None
        ),
    )

    return GetBackupEmailResponse(
        status="success",
        has_backup_email=True,
        data=data,
    )
