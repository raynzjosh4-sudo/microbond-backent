from app.services.communication.sms.constants import SMS_FEE_UGX
from app.services.communication.sms.helpers.send_sms import send_sms


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
    return send_sms(phone_number, message)
