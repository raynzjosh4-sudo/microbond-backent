import base64
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-load brand image assets for inline CID attachments
# ---------------------------------------------------------------------------
_ICON_DIR = Path(__file__).resolve().parent.parent.parent / "icon" / "email_optimized"

def _read_asset(filename: str) -> bytes:
    p = _ICON_DIR / filename
    if not p.exists():
        # Fallback to parent icon directory
        alt = p.parent.parent / filename
        if alt.exists():
            return alt.read_bytes()
        return b""
    return p.read_bytes()

_ICON_BYTES = _read_asset("microbondicon.png")
_CODE_HERO_BYTES = _read_asset("topcodeimage.jpg")
_STMT_HERO_BYTES = _read_asset("attachementtopimage.jpg")
_SECURITY_ALERT_BYTES = _read_asset("securityemailalertimage.jpg")


class EmailNotificationService:
    """
    Central transactional email service backed by Resend (https://resend.com).

    Every method is async so it can be safely handed to FastAPI BackgroundTasks
    without blocking the request/response cycle.

    HTML bodies are produced by the dedicated email_templates module.
    Brand images are automatically attached as inline CID attachments so they
    render seamlessly in Gmail, Outlook, Apple Mail, and mobile clients.
    """

    # ------------------------------------------------------------------
    # Internal dispatch helper
    # ------------------------------------------------------------------
    @staticmethod
    async def _dispatch(
        recipient_email: str,
        subject: str,
        html_body: str,
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None,
    ) -> bool:
        from app.core.config import settings
        import resend

        if not settings.RESEND_API_KEY:
            # Dev / CI: log and pretend it worked
            logger.warning(
                f"[EMAIL_DISPATCH] RESEND_API_KEY not set — email NOT sent. "
                f"Recipient: {recipient_email} | Subject: {subject}"
            )
            return True

        resend.api_key = settings.RESEND_API_KEY

        params: resend.Emails.SendParams = {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [recipient_email],
            "subject": subject,
            "html": html_body,
        }

        # Build attachment list (including automatic CID inline assets)
        attachments = []

        if "cid:microbond_icon" in html_body and _ICON_BYTES:
            attachments.append({
                "filename": "microbondicon.png",
                "content": base64.b64encode(_ICON_BYTES).decode("utf-8"),
                "content_type": "image/png",
                "content_id": "microbond_icon",
                "inline_content_id": "microbond_icon",
            })

        if "cid:code_hero" in html_body and _CODE_HERO_BYTES:
            attachments.append({
                "filename": "topcodeimage.jpg",
                "content": base64.b64encode(_CODE_HERO_BYTES).decode("utf-8"),
                "content_type": "image/jpeg",
                "content_id": "code_hero",
                "inline_content_id": "code_hero",
            })

        if "cid:statement_hero" in html_body and _STMT_HERO_BYTES:
            attachments.append({
                "filename": "attachementtopimage.jpg",
                "content": base64.b64encode(_STMT_HERO_BYTES).decode("utf-8"),
                "content_type": "image/jpeg",
                "content_id": "statement_hero",
                "inline_content_id": "statement_hero",
            })

        if "cid:security_alert_hero" in html_body and _SECURITY_ALERT_BYTES:
            attachments.append({
                "filename": "securityemailalertimage.jpg",
                "content": base64.b64encode(_SECURITY_ALERT_BYTES).decode("utf-8"),
                "content_type": "image/jpeg",
                "content_id": "security_alert_hero",
                "inline_content_id": "security_alert_hero",
            })

        # Add user-provided file attachment (e.g., PDF statement, audit ledger)
        if attachment_bytes and attachment_filename:
            attachments.append({
                "filename": attachment_filename,
                "content": base64.b64encode(attachment_bytes).decode("utf-8"),
            })

        if attachments:
            params["attachments"] = attachments

        try:
            result = resend.Emails.send(params)
            logger.info(
                f"[EMAIL_DISPATCH] Sent via Resend to {recipient_email} | "
                f"Subject: '{subject}' | id={result.get('id', 'n/a')}"
            )
            return True
        except Exception as exc:
            logger.error(
                f"[EMAIL_DISPATCH] Resend send failed for {recipient_email}: {exc}"
            )
            return False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    @classmethod
    async def send_email(
        cls,
        recipient_email: str,
        subject: str,
        html_body: str,
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None,
    ) -> bool:
        return await cls._dispatch(
            recipient_email, subject, html_body, attachment_bytes, attachment_filename
        )

    # ------------------------------------------------------------------
    # Branded high-level methods
    # ------------------------------------------------------------------
    @classmethod
    async def send_security_alert_new_device(
        cls,
        recipient_email: str,
        phone_number: str,
        new_device_id: str,
        cooldown_hours: int = 48,
    ):
        """Out-of-band security alert when an account is accessed from a foreign device."""
        from app.services.communication.email_templates import security_alert_new_device
        subject = "Security Alert: New Device Login on Your Microbond Account"
        body = security_alert_new_device(phone_number, new_device_id, cooldown_hours)
        return await cls._dispatch(recipient_email, subject, body)

    @classmethod
    async def send_kyc_rejection_guidance(
        cls,
        recipient_email: str,
        rejection_reason: str,
        guidance_notes: str,
    ):
        """Actionable KYC correction guidance email."""
        from app.services.communication.email_templates import kyc_rejection_guidance
        subject = "Action Required: Update Your Microbond Identity Verification"
        body = kyc_rejection_guidance(rejection_reason, guidance_notes)
        return await cls._dispatch(recipient_email, subject, body)

    @classmethod
    async def send_audit_report(
        cls,
        recipient_email: str,
        group_title: str,
        file_format: str,
        file_bytes: bytes,
    ):
        """Dispatches the formal group audit ledger as an email attachment."""
        from app.services.communication.email_templates import audit_report
        subject = f"Audit Report & Financial Ledger: {group_title}"
        filename = f"{group_title.replace(' ', '_')}_Audit_Ledger.{file_format.lower()}"
        body = audit_report(group_title)
        return await cls._dispatch(
            recipient_email=recipient_email,
            subject=subject,
            html_body=body,
            attachment_bytes=file_bytes,
            attachment_filename=filename,
        )

    @classmethod
    async def send_otp_email(
        cls,
        recipient_email: str,
        otp_code: str,
        purpose: str = "Login",
    ):
        """Sends a one-time verification code to the user's email."""
        from app.services.communication.email_templates import otp_code as otp_template
        subject = f"Your Microbond {purpose} Code"
        body = otp_template(otp_code, purpose)
        return await cls._dispatch(recipient_email, subject, body)

    @classmethod
    async def send_security_alert_email_takeover_attempt(
        cls,
        recipient_email: str,
        code: str,
        attempting_phone: str,
    ):
        """Dispatches an alert when another phone number tries to link an existing verified email."""
        from app.services.communication.email_templates import security_alert_email_takeover_attempt
        subject = "Security Alert: Attempt to Link Your Microbond Backup Email"
        body = security_alert_email_takeover_attempt(code, recipient_email, attempting_phone)
        return await cls._dispatch(recipient_email, subject, body)

    @classmethod
    async def send_security_email_unlinked_notification(
        cls,
        recipient_email: str,
        new_account_phone: str,
    ):
        """Dispatches a notification when an email is transferred to another account and unlinked from the old account."""
        from app.services.communication.email_templates import security_email_unlinked_notification
        subject = "Security Notice: Your Microbond Backup Email Has Been Transferred"
        body = security_email_unlinked_notification(recipient_email, new_account_phone)
        return await cls._dispatch(recipient_email, subject, body)

