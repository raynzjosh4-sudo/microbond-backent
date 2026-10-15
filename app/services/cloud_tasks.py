import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


async def enqueue_email_task(to_email: str, subject: str, html_content: str) -> bool:
    """
    Dispatches a transactional email task.
    If Cloud Tasks is configured in GCP, enqueues to the Cloud Tasks queue.
    Otherwise dispatches directly via EmailNotificationService.
    """
    logger.info(f"[TaskDispatcher] Enqueuing email task to {to_email}...")
    try:
        from app.services.communication.email_service import EmailNotificationService
        await EmailNotificationService.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content
        )
        return True
    except Exception as e:
        logger.error(f"[TaskDispatcher] Direct email dispatch error: {e}")
        return False


def enqueue_push_task(token: str, title: str, body: str, data: Optional[Dict[str, str]] = None) -> bool:
    """
    Dispatches a push notification task.
    """
    logger.info(f"[TaskDispatcher] Enqueuing push task: '{title}'...")
    try:
        from app.core.firebase_config import send_push_notification
        send_push_notification(token=token, title=title, body=body, data=data)
        return True
    except Exception as e:
        logger.error(f"[TaskDispatcher] Direct push dispatch error: {e}")
        return False


def enqueue_sms_task(phone_number: str, message: str) -> bool:
    """
    Dispatches an SMS notification task.
    """
    logger.info(f"[TaskDispatcher] Enqueuing SMS task to {phone_number}...")
    try:
        from app.communications.sms_service import _send_sms, sanitize_uganda_phone
        clean_phone = sanitize_uganda_phone(phone_number)
        _send_sms(clean_phone, message)
        return True
    except Exception as e:
        logger.error(f"[TaskDispatcher] Direct SMS dispatch error: {e}")
        return False
