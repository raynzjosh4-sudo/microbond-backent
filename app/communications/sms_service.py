import africastalking
from app.core.config import settings

USERNAME = settings.AT_USERNAME
API_KEY = settings.AT_API_KEY

if USERNAME and API_KEY:
    africastalking.initialize(USERNAME, API_KEY)
    sms = africastalking.SMS
else:
    sms = None

SMS_FEE_UGX = 50  # Flat fee charged per-deposit when SMS reminders are enabled

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

def _send_sms(phone_number: str, message: str) -> bool:
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

def send_real_otp_sms(phone_number: str, code: str) -> bool:
    message = f"Your Microbond code is: {code}. Valid for 5 minutes. Do not share it."
    return _send_sms(phone_number, message)

def send_overdue_reminder_sms(
    phone_number: str,
    member_name: str,
    group_name: str,
    amount_due: int,
    currency: str = "UGX"
) -> bool:
    """
    Sent when a member's payment is overdue and the group has SMS reminders enabled.
    Called AFTER the email attempt (if the member has a security email).
    """
    message = (
        f"Hi {member_name}, your Microbond payment of {currency} {amount_due:,} "
        f"for group '{group_name}' is overdue. Please pay now to avoid late fees. "
        f"Open the Microbond app to pay."
    )
    return _send_sms(phone_number, message)

def send_deposit_receipt_sms(
    phone_number: str,
    member_name: str,
    group_name: str,
    amount_deposited: int,
    sms_fee: int = SMS_FEE_UGX,
    currency: str = "UGX"
) -> bool:
    """
    Sent immediately after a member successfully deposits into a group.
    Includes a note that a 50 UGX SMS fee is added to their next deposit.
    """
    message = (
        f"Hi {member_name}, your deposit of {currency} {amount_deposited:,} "
        f"into '{group_name}' was received. "
        f"Note: A {currency} {sms_fee} SMS notification fee will be added to your next deposit."
    )
    return _send_sms(phone_number, message)

def send_sms_opt_in_consent_notice(
    phone_number: str,
    member_name: str,
    group_name: str,
    sms_fee: int = SMS_FEE_UGX,
    currency: str = "UGX"
) -> bool:
    """
    Sent once when a member first enables SMS reminders so they know about the fee.
    """
    message = (
        f"Hi {member_name}, you've enabled SMS reminders for '{group_name}' on Microbond. "
        f"A fee of {currency} {sms_fee} will be deducted from each future deposit you make. "
        f"To opt out, open group settings in the Microbond app."
    )
    return _send_sms(phone_number, message)
