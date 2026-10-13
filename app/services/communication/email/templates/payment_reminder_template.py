from app.services.communication.email.templates.layout import wrap, _PAYMENT_REMINDER_HERO_URL


def build_overdue_reminder_email(
    member_name: str,
    group_name: str,
    amount_due: int,
    currency: str = "UGX"
) -> str:
    """
    Sent when a member's group payment goes overdue.
    Email is dispatched first; SMS follows only if the member has opted in.
    """
    inner = f"""
        <h2>Payment Overdue — Action Required</h2>
        <p>Hi <strong>{member_name}</strong>,</p>
        <p>Your payment for the group <strong>"{group_name}"</strong> is now <strong>overdue</strong>.</p>
        <hr class="divider" />
        <table width="100%" style="margin: 18px 0; border-radius: 8px; background: #fef2f2; padding: 16px; border-left: 4px solid #dc2626;">
            <tr>
                <td style="font-size: 14px; color: #991b1b;">
                    <strong>Amount Due:</strong> {currency} {amount_due:,}
                </td>
            </tr>
        </table>
        <p>Please open the <strong>Microbond app</strong> and make your payment as soon as possible to avoid additional late fees.</p>
        <p>If you have already made this payment, please ignore this message — our system will update shortly.</p>
        <hr class="divider" />
        <p class="sm">You received this email because your Microbond account has a verified backup email and the group admin has enabled overdue payment reminders.</p>
    """
    return wrap(_PAYMENT_REMINDER_HERO_URL, inner, subtitle="Payment Reminder")
