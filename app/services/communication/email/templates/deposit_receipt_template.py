from app.services.communication.email.templates.layout import wrap, _STMT_HERO_URL


def build_deposit_receipt_email(
    member_name: str,
    group_name: str,
    amount_deposited: int,
    sms_fee_ugx: int = 50,
    currency: str = "UGX"
) -> str:
    """
    Sent after a successful deposit when the member has a verified security email.
    Includes the SMS fee notice.
    """
    inner = f"""
        <h2>Deposit Received ✓</h2>
        <p>Hi <strong>{member_name}</strong>,</p>
        <p>Your deposit of <strong>{currency} {amount_deposited:,}</strong> into the group <strong>"{group_name}"</strong> was received successfully.</p>
        <hr class="divider" />
        <p style="font-size: 13px; color: #6b7280;">
            <strong>SMS Notification Fee:</strong> A fee of <strong>{currency} {sms_fee_ugx}</strong> for this SMS notification
            has been added to your account and will be deducted from your next deposit.
            You can opt out of SMS reminders at any time in your group membership settings.
        </p>
    """
    return wrap(_STMT_HERO_URL, inner, subtitle="Deposit Confirmation")
