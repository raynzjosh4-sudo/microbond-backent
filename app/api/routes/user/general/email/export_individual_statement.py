from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.security_email import UserSecurityEmail
from app.services.communication.email_service import EmailNotificationService
from app.services.communication import email_templates
from .schemas import ExportStatementRequest

router = APIRouter()


@router.post(
    "/export-statement",
    summary="Export Individual Regulatory Statement",
    description="Compiles official regulatory statement and delivers it to the user's verified backup email.",
)
async def export_individual_statement(
    payload: ExportStatementRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    sec_email = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.user_id == current_user.id,
            UserSecurityEmail.is_verified == True,
        )
    ).first()

    if not sec_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A verified backup email is required to receive official statements.",
        )

    dummy_statement_pdf = (
        b"%PDF-1.4 Mock Regulatory Statement for User "
        + str(current_user.id).encode()
    )

    subject = "Your Official Microbond Account Statement"
    body = email_templates.account_statement(
        current_user.full_name, payload.months_back
    )

    background_tasks.add_task(
        EmailNotificationService.send_email,
        sec_email.email,
        subject,
        body,
        dummy_statement_pdf,
        f"Microbond_Statement_{current_user.phone_number}.pdf",
    )

    return {
        "status": "success",
        "message": f"Your regulatory account statement has been dispatched to {sec_email.email}.",
    }
