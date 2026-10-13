import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.models.user.user import User
from app.services.communication.email_service import EmailNotificationService
from .schemas import KYCDecisionWebhookRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decision", tags=["KYC Decision & Feedback"])


@router.post(
    "/webhook",
    summary="KYC Verification Decision Hook",
    description="Processes internal/provider KYC verification results. If rejected, triggers actionable feedback email to user.",
)
async def process_kyc_decision(
    payload: KYCDecisionWebhookRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    try:
        user_uuid = uuid.UUID(payload.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format.")

    user = session.exec(select(User).where(User.id == user_uuid)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.decision.upper() == "APPROVED":
        user.kyc_status = "VERIFIED"
        user.kyc_tier = max(user.kyc_tier, 2)
        user.is_verified = True
        session.add(user)
        session.commit()
        return {"status": "success", "message": "User KYC verified successfully."}

    elif payload.decision.upper() == "REJECTED":
        user.kyc_status = "REJECTED"
        session.add(user)
        session.commit()

        # Fire actionable guidance email if verified backup email exists
        from app.models.user.security_email import UserSecurityEmail

        sec_email = session.exec(
            select(UserSecurityEmail).where(
                UserSecurityEmail.user_id == user.id,
                UserSecurityEmail.is_verified == True,
            )
        ).first()

        if sec_email:
            reason = (
                payload.rejection_reason
                or "Document photo was unreadable or information mismatched."
            )
            guidance = (
                payload.guidance_notes
                or "Please ensure there is no glare on your National ID and that all corners of the card are visible."
            )
            background_tasks.add_task(
                EmailNotificationService.send_kyc_rejection_guidance,
                sec_email.email,
                reason,
                guidance,
            )

        return {
            "status": "success",
            "message": "User KYC rejection processed and actionable feedback dispatched.",
        }

    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid decision value. Must be APPROVED or REJECTED.",
        )
