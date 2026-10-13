from app.services.communication.email.templates.layout import wrap, _CODE_HERO_URL


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
    return wrap(_CODE_HERO_URL, inner, subtitle="Verification Update")
