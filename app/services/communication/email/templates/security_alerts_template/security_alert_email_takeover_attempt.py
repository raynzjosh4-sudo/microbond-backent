from app.services.communication.email.templates.layout import wrap, _SECURITY_HERO_URL


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
