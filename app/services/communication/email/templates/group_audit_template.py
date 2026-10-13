from app.services.communication.email.templates.layout import wrap, _STMT_HERO_URL


def audit_report(group_title: str) -> str:
    """Formal group audit ledger dispatch email."""
    inner = f"""
        <h2>Group audit report</h2>
        <p>The compiled financial audit ledger for <strong>{group_title}</strong> is attached to this email.</p>
        <hr class="divider" />
        <p class="sm">Includes complete double-entry journals, group contributions, and escrow balances. Contact your group administrator if you notice any discrepancies.</p>
    """
    return wrap(_STMT_HERO_URL, inner, subtitle="Audit Report")
