"""
Microbond Email HTML Templates — Clean Minimal Style
-----------------------------------------------------
Stripe/Linear-inspired transactional email design:
- White card on light grey background, no colored boxes
- Small logo at top, plain readable text body
- One clean bold code block, tight spacing
- Images referenced via public HTTPS URL (no CID attachments)
  → upload app/icon/email_optimized/ files to Supabase bucket "email-assets"
"""

from datetime import datetime, timezone
from app.core.config import settings

# Derive image URLs from Supabase public storage bucket
# Format: https://<project-ref>.supabase.co/storage/v1/object/public/email-assets
_BASE = getattr(settings, "EMAIL_ASSET_BASE_URL", "").rstrip("/")
_ICON_URL          = f"{_BASE}/microbondicon.png"
_CODE_HERO_URL             = f"{_BASE}/topcodeimage.jpg"
_STMT_HERO_URL             = f"{_BASE}/attachementtopimage.jpg"
_SECURITY_HERO_URL         = f"{_BASE}/securityemailalertimage.jpg"
_PAYMENT_REMINDER_HERO_URL = f"{_BASE}/emailpaymentremainderimage.jpg"


_BRAND      = "#075E54"
_TEXT       = "#111827"
_MUTED      = "#6B7280"
_BORDER     = "#E5E7EB"

_BASE_STYLES = f"""
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0; padding: 0;
        background-color: #f3f4f6;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        -webkit-font-smoothing: antialiased;
        color: {_TEXT};
    }}
    table {{ border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
    td {{ padding: 0; }}
    .wrap {{
        width: 100%; max-width: 520px;
        margin: 0 auto;
        background-color: #ffffff;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid {_BORDER};
    }}
    .hero-img {{
        width: 100%; max-width: 520px; height: auto;
        display: block; border: 0;
    }}
    .logo-row {{
        padding: 20px 28px;
        border-bottom: 1px solid {_BORDER};
    }}
    .body-cell {{ padding: 28px 28px 4px 28px; }}
    .body-cell h2 {{
        margin: 0 0 10px 0;
        font-size: 19px;
        font-weight: 700;
        color: {_TEXT};
        line-height: 1.35;
    }}
    .body-cell p {{
        margin: 0 0 14px 0;
        font-size: 15px;
        line-height: 1.6;
        color: {_TEXT};
    }}
    .body-cell p.sm {{
        font-size: 13px;
        color: {_MUTED};
    }}
    hr.divider {{
        border: none;
        border-top: 1px solid {_BORDER};
        margin: 18px 0;
    }}
    .code-block {{
        background-color: #f9fafb;
        border: 1px solid {_BORDER};
        border-radius: 6px;
        text-align: center;
        padding: 16px 12px;
        margin: 18px 0;
    }}
    .code-label {{
        display: block;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        color: {_MUTED};
        margin-bottom: 8px;
    }}
    .code-digits {{
        display: block;
        font-size: 34px;
        font-weight: 800;
        letter-spacing: 8px;
        color: {_BRAND};
    }}
    .btn {{
        display: inline-block;
        background-color: {_BRAND};
        color: #ffffff !important;
        text-decoration: none;
        padding: 10px 22px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 600;
    }}
    .btn-red {{
        display: inline-block;
        background-color: #DC2626;
        color: #ffffff !important;
        text-decoration: none;
        padding: 10px 22px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 600;
    }}
    .footer-cell {{
        padding: 18px 28px 24px 28px;
        border-top: 1px solid {_BORDER};
    }}
    .footer-cell p {{
        margin: 0 0 4px 0;
        font-size: 12px;
        line-height: 1.6;
        color: {_MUTED};
    }}
    .footer-cell a {{ color: {_BRAND}; text-decoration: none; }}
"""


def _get_year() -> int:
    return datetime.now(timezone.utc).year


def _wrap(hero_url: str, inner_html: str, subtitle: str = "Notification") -> str:
    """Wrap content in the clean minimal Stripe-style email layout."""
    hero_section = ""
    if hero_url:
        hero_section = (
            f'<tr><td><img src="{hero_url}" alt="" class="hero-img" /></td></tr>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Microbond</title>
<style>{_BASE_STYLES}</style>
</head>
<body style="margin:0;padding:24px 0;background-color:#f3f4f6;">
<table cellpadding="0" cellspacing="0" border="0" width="100%">
<tr><td align="center" style="padding:0 16px;">
<table class="wrap" cellpadding="0" cellspacing="0" border="0" width="100%">
  <tr>
    <td class="logo-row">
      <table cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="padding-right:10px;vertical-align:middle;">
            <img src="{_ICON_URL}" alt="M" width="30" height="30"
                 style="display:block;border-radius:6px;" />
          </td>
          <td style="vertical-align:middle;">
            <span style="font-size:15px;font-weight:700;color:{_BRAND};">Microbond</span>
            <span style="font-size:12px;color:{_MUTED};margin-left:6px;">&middot; {subtitle}</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  {hero_section}
  <tr><td class="body-cell">{inner_html}</td></tr>
  <tr>
    <td class="footer-cell">
      <p>This is an automated message from <a href="https://www.microbond.co">Microbond</a>. Do not reply.</p>
      <p>Never share your code with anyone. Microbond staff will never ask for it.</p>
      <p style="margin-top:8px;">&copy; {_get_year()} Microbond &middot; Official Financial Records</p>
    </td>
  </tr>
</table>
</td></tr>
</table>
</body>
</html>"""


# =========================================================================
# PUBLIC TEMPLATE FUNCTIONS
# =========================================================================

def verification_code(code: str, recipient_email: str) -> str:
    """Email verification / backup-email OTP code."""
    inner = f"""
        <h2>Verify your email</h2>
        <p>Enter the code below to confirm <strong>{recipient_email}</strong> as your Microbond backup email address.</p>
        <div class="code-block">
            <span class="code-label">Verification Code</span>
            <span class="code-digits">{code}</span>
        </div>
        <p class="sm">Valid for 15 minutes. If you did not request this, you can safely ignore this email.</p>
    """
    return _wrap(_CODE_HERO_URL, inner, subtitle="Email Verification")


def otp_code(code: str, purpose: str = "Login") -> str:
    """General one-time password email."""
    inner = f"""
        <h2>Your {purpose} code</h2>
        <p>Use the code below to complete your <strong>{purpose}</strong> on Microbond.</p>
        <div class="code-block">
            <span class="code-label">{purpose} Code</span>
            <span class="code-digits">{code}</span>
        </div>
        <p class="sm">Valid for 10 minutes. Do not share this code with anyone.</p>
    """
    return _wrap(_CODE_HERO_URL, inner, subtitle="One-Time Code")


def account_statement(full_name: str, months_back: int) -> str:
    """Official regulatory account statement email."""
    name = full_name or "Member"
    plural = "s" if months_back != 1 else ""
    inner = f"""
        <h2>Your account statement</h2>
        <p>Hi <strong>{name}</strong>,</p>
        <p>Your official Microbond statement for the past <strong>{months_back} month{plural}</strong> is attached to this email.</p>
        <hr class="divider" />
        <p class="sm">This document is cryptographically certified by Microbond for accounting and regulatory compliance. You can also review your full history inside the Microbond app.</p>
    """
    return _wrap(_STMT_HERO_URL, inner, subtitle="Account Statement")


def security_alert_new_device(phone_number: str, new_device_id: str, cooldown_hours: int = 48) -> str:
    """Security alert for unrecognized device login."""
    inner = f"""
        <h2>New device login detected</h2>
        <p>Your Microbond account (<strong>{phone_number}</strong>) was just accessed from an unrecognized device.</p>
        <hr class="divider" />
        <p><strong>Device:</strong> {new_device_id}</p>
        <p><strong>Protection active:</strong> A <strong>{cooldown_hours}-hour cooldown</strong> has been placed on payouts and withdrawals as a precaution.</p>
        <hr class="divider" />
        <p>If you did not authorize this, freeze your account immediately.</p>
        <p style="margin-top:16px;">
            <a href="https://app.microbond.io/security/freeze-account" class="btn-red">Freeze Account</a>
        </p>
        <p class="sm" style="margin-top:18px;">If this was you, no action is needed.</p>
    """
    return _wrap(_SECURITY_HERO_URL, inner, subtitle="Security Alert")


def kyc_rejection_guidance(rejection_reason: str, guidance_notes: str) -> str:
    """Actionable KYC correction guidance email."""
    inner = f"""
        <h2>Identity verification update required</h2>
        <p>We reviewed your recent verification documents but need a few updates before we can approve your account.</p>
        <hr class="divider" />
        <p><strong>Issue:</strong> {rejection_reason}</p>
        <p><strong>What to do:</strong> {guidance_notes}</p>
        <hr class="divider" />
        <p style="margin-top:4px;">
            <a href="microbond://kyc/reverify" class="btn">Update in App</a>
        </p>
    """
    return _wrap(_CODE_HERO_URL, inner, subtitle="Verification Update")


def audit_report(group_title: str) -> str:
    """Formal group audit ledger dispatch email."""
    inner = f"""
        <h2>Group audit report</h2>
        <p>The compiled financial audit ledger for <strong>{group_title}</strong> is attached to this email.</p>
        <hr class="divider" />
        <p class="sm">Includes complete double-entry journals, group contributions, and escrow balances. Contact your group administrator if you notice any discrepancies.</p>
    """
    return _wrap(_STMT_HERO_URL, inner, subtitle="Audit Report")


def security_alert_email_takeover_attempt(code: str, target_email: str, attempting_phone: str) -> str:
    """Security alert when another account attempts to link an already-verified email."""
    inner = f"""
        <h2>Someone is trying to link your email</h2>
        <p>A Microbond account with phone number <strong>{attempting_phone}</strong> has requested to link <strong>{target_email}</strong> to their account.</p>
        <hr class="divider" />
        <p><strong>Is this you?</strong> If you own both accounts and want to transfer this backup email, enter the code below on the other account. <strong>This will disconnect the email from your current account.</strong></p>
        <div class="code-block">
            <span class="code-label">Transfer Verification Code</span>
            <span class="code-digits">{code}</span>
        </div>
        <p><strong>Not you?</strong> Do not share this code with anyone. Without it, no one can link or take over your email address. Your current account remains fully protected.</p>
        <p class="sm" style="margin-top:14px;">Valid for 15 minutes.</p>
    """
    return _wrap(_SECURITY_HERO_URL, inner, subtitle="Security Alert")


def security_email_unlinked_notification(unlinked_email: str, new_account_phone: str) -> str:
    """Notification when an email is transferred to a new account."""
    inner = f"""
        <h2>Your backup email was transferred</h2>
        <p>Your backup email address <strong>{unlinked_email}</strong> has been verified on another Microbond account (<strong>{new_account_phone}</strong>).</p>
        <hr class="divider" />
        <p>For your security, this email has been disconnected from your previous account. Only one account can hold a verified email at a time.</p>
        <p>If you did not authorize this, please freeze your account and contact Microbond support immediately.</p>
    """
    return _wrap(_SECURITY_HERO_URL, inner, subtitle="Security Notice")


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
    return _wrap(_PAYMENT_REMINDER_HERO_URL, inner, subtitle="Payment Reminder")


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
    return _wrap(_STMT_HERO_URL, inner, subtitle="Deposit Confirmation")


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
    return _wrap(_STMT_HERO_URL, inner, subtitle="Payout Confirmation")


