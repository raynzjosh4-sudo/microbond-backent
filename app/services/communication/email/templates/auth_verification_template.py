from app.services.communication.email.templates.layout import wrap, _CODE_HERO_URL


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
    return wrap(_CODE_HERO_URL, inner, subtitle="Email Verification")


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
    return wrap(_CODE_HERO_URL, inner, subtitle="One-Time Code")
