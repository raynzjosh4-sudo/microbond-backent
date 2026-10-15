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
