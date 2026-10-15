import logging
from fastapi import APIRouter, Depends, HTTPException
from app.core.internal_auth import verify_internal_task_request
from app.services.communication.email_service import EmailNotificationService
from .schemas import SendEmailTaskRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/send-email",
    summary="Cloud Tasks Trigger: Asynchronous verified email delivery",
    dependencies=[Depends(verify_internal_task_request)]
)
async def send_email(request: SendEmailTaskRequest):
    """
    Invoked asynchronously by Google Cloud Tasks.
    Dispatches verified transactional emails via Resend with automatic retries.
    """
    logger.info(f"[InternalTask] Delivering transactional email to {request.to_email}...")
    try:
        await EmailNotificationService.send_email(
            to_email=request.to_email,
            subject=request.subject,
            html_content=request.html_content
        )
        return {"status": "success", "recipient": request.to_email}
    except Exception as e:
        logger.error(f"[InternalTask] Failed delivering email to {request.to_email}: {e}")
        # Raising 500 signals Cloud Tasks to retry with exponential backoff
        raise HTTPException(status_code=500, detail="Email delivery failure. Task will be retried.")
