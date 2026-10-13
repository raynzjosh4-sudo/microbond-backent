from app.services.communication.email.templates.layout import wrap, _STMT_HERO_URL


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
    return wrap(_STMT_HERO_URL, inner, subtitle="Account Statement")
