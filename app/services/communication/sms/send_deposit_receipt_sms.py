from app.services.communication.sms.constants import SMS_FEE_UGX
from app.services.communication.sms.helpers.send_sms import send_sms


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
    return send_sms(phone_number, message)
