import logging
from fastapi import APIRouter, Depends
from app.core.internal_auth import verify_internal_task_request
from app.core.firebase_config import send_push_notification
from .schemas import SendPushTaskRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/send-push",
    summary="Cloud Tasks Trigger: Asynchronous FCM push notification delivery",
    dependencies=[Depends(verify_internal_task_request)]
)
def send_push(request: SendPushTaskRequest):
    """
    Invoked asynchronously by Google Cloud Tasks.
    Sends push notifications to Android client via Firebase Cloud Messaging.
    """
    logger.info(f"[InternalTask] Delivering push notification '{request.title}'...")
    response = send_push_notification(
        token=request.token,
        title=request.title,
        body=request.body,
        data=request.data
    )
    if response is None:
        logger.warning(f"[InternalTask] Push notification delivery failed for token {request.token[:10]}...")
        # Note: Do not hard-fail invalid/expired tokens, but record failure
        return {"status": "failed", "detail": "FCM delivery rejected token"}

    return {"status": "success", "fcm_message_id": str(response)}
