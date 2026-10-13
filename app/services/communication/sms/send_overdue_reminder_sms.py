from app.services.communication.sms.helpers.send_sms import send_sms


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
    return send_sms(phone_number, message)
