from app.services.communication.email.templates.layout import wrap, _SECURITY_HERO_URL


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
    return wrap(_SECURITY_HERO_URL, inner, subtitle="Security Alert")


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
    return wrap(_SECURITY_HERO_URL, inner, subtitle="Security Alert")


def security_email_unlinked_notification(unlinked_email: str, new_account_phone: str) -> str:
    """Notification when an email is transferred to a new account."""
    inner = f"""
        <h2>Your backup email was transferred</h2>
        <p>Your backup email address <strong>{unlinked_email}</strong> has been verified on another Microbond account (<strong>{new_account_phone}</strong>).</p>
        <hr class="divider" />
        <p>For your security, this email has been disconnected from your previous account. Only one account can hold a verified email at a time.</p>
        <p>If you did not authorize this, please freeze your account and contact Microbond support immediately.</p>
    """
    return wrap(_SECURITY_HERO_URL, inner, subtitle="Security Notice")
