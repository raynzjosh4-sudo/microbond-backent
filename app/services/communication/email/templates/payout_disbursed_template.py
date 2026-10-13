from app.services.communication.email.templates.layout import wrap, _STMT_HERO_URL


def build_payout_disbursed_email(
    member_name: str,
    group_name: str,
    amount_paid: int,
    cycle_number: int,
    provider_name: str,
    masked_account: str,
    currency: str = "UGX"
) -> str:
    """
    Sent when a group payout is successfully disbursed to the member's chosen account.
    """
    inner = f"""
        <h2>Payout Disbursed 🎉</h2>
        <p>Hi <strong>{member_name}</strong>,</p>
        <p>Great news! Your payout for Round <strong>{cycle_number}</strong> of <strong>"{group_name}"</strong> has been sent to your chosen account.</p>
        <hr class="divider" />
        <table width="100%" style="margin: 18px 0; border-radius: 8px; background: #f0fdf4; padding: 16px; border-left: 4px solid #16a34a;">
            <tr>
                <td style="font-size: 15px; color: #166534;">
                    <strong>Amount Disbursed:</strong> {currency} {amount_paid:,}<br/>
                    <strong>Destination:</strong> {provider_name} ({masked_account})
                </td>
            </tr>
        </table>
        <p>The funds should reflect in your account immediately or within a few minutes depending on telecom network processing.</p>
        <hr class="divider" />
        <p class="sm">You received this notification because you have a verified security email linked to your Microbond account.</p>
    """
    return wrap(_STMT_HERO_URL, inner, subtitle="Payout Confirmation")
