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
    """Return whether Africa's Talking accepted the SMS, not carrier delivery."""
    if not sms:
        logger.error("Africa's Talking API key or username is not configured.")
        return False

    try:
        response = sms.send(message, [sanitize_uganda_phone(phone_number)])
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
