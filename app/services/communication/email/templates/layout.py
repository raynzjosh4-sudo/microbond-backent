from datetime import datetime, timezone
from app.core.config import settings

_BASE = getattr(settings, "EMAIL_ASSET_BASE_URL", "").rstrip("/")
_ICON_URL                  = f"{_BASE}/microbondicon.png"
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


def get_year() -> int:
    return datetime.now(timezone.utc).year


def wrap(hero_url: str, inner_html: str, subtitle: str = "Notification") -> str:
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
      <p style="margin-top:8px;">&copy; {get_year()} Microbond &middot; Official Financial Records</p>
    </td>
  </tr>
</table>
</td></tr>
</table>
</body>
</html>"""
