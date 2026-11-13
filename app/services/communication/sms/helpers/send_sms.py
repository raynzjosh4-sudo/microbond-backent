import logging

import africastalking
from app.core.config import settings
from app.utils.phone.sanitize_uganda_phone import sanitize_uganda_phone

logger = logging.getLogger(__name__)

sms = None


def get_sms_client():
    """Return the configured Africa's Talking SMS client, creating it lazily."""
    global sms

    username = settings.AT_USERNAME
    api_key = settings.AT_API_KEY
    if not username or not api_key:
        sms = None
        return None

    if sms is None:
        try:
            africastalking.initialize(username, api_key)
            sms = africastalking.SMS
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("Africa's Talking SMS client setup failed (%s).", type(exc).__name__)
            sms = None
            return None

    return sms


def send_sms(phone_number: str, message: str) -> bool:
    """Return whether Africa's Talking accepted the SMS, not carrier delivery."""
    try:
        sanitized_phone = sanitize_uganda_phone(phone_number)
    except Exception as exc:
        logger.error("Invalid phone number for SMS delivery (%s).", exc)
        return False

    client = get_sms_client()
    if not client:
        logger.error("Africa's Talking API key or username is not configured.")
        return False

    try:
        response = client.send(message, [sanitized_phone])
    except Exception as exc:
        logger.error("Africa's Talking SMS request failed (%s).", type(exc).__name__)
        return False

    sms_data = response.get("SMSMessageData") if isinstance(response, dict) else None
    recipients = sms_data.get("Recipients") if isinstance(sms_data, dict) else None
    if not isinstance(recipients, list) or not recipients:
        logger.warning("Africa's Talking returned an unrecognized SMS response.")
        return False

    accepted_status_codes = {100, 101, 102}
    for recipient in recipients:
        status_code = recipient.get("statusCode") if isinstance(recipient, dict) else None
        try:
            accepted = int(status_code) in accepted_status_codes
        except (TypeError, ValueError):
            accepted = False

        if not accepted:
            logger.warning(
                "Africa's Talking did not accept SMS recipient (status code: %s).",
                status_code,
            )
            return False

    return True
