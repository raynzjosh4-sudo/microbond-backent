import logging
from fastapi import APIRouter, Depends, HTTPException
from app.core.internal_auth import verify_internal_task_request
from app.communications.sms_service import _send_sms, sanitize_uganda_phone
from .schemas import SendSMSTaskRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/send-sms",
    summary="Cloud Tasks Trigger: Asynchronous SMS text message delivery",
    dependencies=[Depends(verify_internal_task_request)]
)
def send_sms(request: SendSMSTaskRequest):
    """
    Invoked asynchronously by Google Cloud Tasks.
    Sends SMS alerts via Africa's Talking gateway.
    """
    try:
        clean_phone = sanitize_uganda_phone(request.phone_number)
    except Exception as e:
        logger.error(f"[InternalTask] Invalid phone number provided for SMS: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid phone number: {e}")

    logger.info(f"[InternalTask] Delivering SMS to {clean_phone}...")
    try:
        response = _send_sms(clean_phone, request.message)
        return {"status": "success", "recipient": clean_phone, "gateway_response": str(response)}
    except Exception as e:
        logger.error(f"[InternalTask] Africa's Talking SMS delivery error: {e}")
        # Raising 500 triggers Cloud Tasks exponential retry
        raise HTTPException(status_code=500, detail="SMS gateway temporary failure. Task will be retried.")
