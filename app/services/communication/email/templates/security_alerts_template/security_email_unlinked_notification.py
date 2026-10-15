from app.services.communication.email.templates.layout import wrap, _SECURITY_HERO_URL


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
