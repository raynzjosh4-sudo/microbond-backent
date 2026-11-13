import logging

import africastalking
from app.core.config import settings
from app.utils.phone.sanitize_uganda_phone import sanitize_uganda_phone

logger = logging.getLogger(__name__)

USERNAME = settings.AT_USERNAME
API_KEY = settings.AT_API_KEY

if USERNAME and API_KEY:
    africastalking.initialize(USERNAME, API_KEY)
    sms = africastalking.SMS
else:
    sms = None


def send_sms(phone_number: str, message: str) -> bool:
    """Internal helper — formats phone, sends via Africa's Talking."""
    if not sms:
        print("[SMS ERROR] Africa's Talking API key or Username not configured.")
        return False
    formatted_phone = sanitize_uganda_phone(phone_number)
    try:
        sms.send(message, [formatted_phone])
        return True
    except Exception as exc:
        logger.error("Africa's Talking SMS request failed (%s).", type(exc).__name__)
        return False
