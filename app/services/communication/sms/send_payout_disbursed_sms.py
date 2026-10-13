from app.services.communication.sms.helpers.send_sms import send_sms


def send_payout_disbursed_sms(
    phone_number: str,
    member_name: str,
    group_name: str,
    amount_paid: int,
    provider_name: str,
    masked_account: str,
    currency: str = "UGX"
) -> bool:
    """
    Sent when the background worker disburses a group payout to the member's chosen account.
    """
    message = (
        f"Microbond: Hi {member_name}, your payout of {currency} {amount_paid:,} "
        f"for group '{group_name}' has been sent to your {provider_name} ({masked_account})."
    )
    return send_sms(phone_number, message)
