import africastalking
from app.core.config import settings

USERNAME = settings.AT_USERNAME
API_KEY = settings.AT_API_KEY

if USERNAME and API_KEY:
    africastalking.initialize(USERNAME, API_KEY)
    sms = africastalking.SMS
else:
    sms = None

def sanitize_uganda_phone(phone: str) -> str:
    """
    Formats local Ugandan inputs (0771234567, 0701234567, 25677...) 
    into standard E.164 (+256771234567).
    """
    clean = phone.strip().replace(" ", "").replace("-", "")
    if clean.startswith("07"):
        return "+256" + clean[1:]
    if clean.startswith("256"):
        return "+" + clean
    if not clean.startswith("+"):
        return "+" + clean
    return clean

def send_real_otp_sms(phone_number: str, code: str) -> bool:
    if not sms:
        print("[SMS ERROR] Africa's Talking API key or Username not configured.")
        return False

    formatted_phone = sanitize_uganda_phone(phone_number)
    message = f"Your Microbond code is: {code}. Valid for 5 minutes. Do not share it."

    try:
        response = sms.send(message, [formatted_phone])
        print(f"[AT LIVE SMS RESPONSE]: {response}")
        return True
    except Exception as e:
        print(f"[AT SMS ERROR]: {str(e)}")
        return False
