import africastalking
from app.core.config import settings
from app.utils.phone.sanitize_uganda_phone import sanitize_uganda_phone

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
        response = sms.send(message, [formatted_phone])
        print(f"[AT LIVE SMS RESPONSE]: {response}")
        return True
    except Exception as e:
        print(f"[AT SMS ERROR]: {str(e)}")
        return False
