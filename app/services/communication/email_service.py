import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

class EmailNotificationService:
    """
    Central service for dispatching transactional, security, and audit emails.
    Can be backed by SendGrid, AWS SES, or SMTP.
    """

    @staticmethod
    async def send_email(
        recipient_email: str,
        subject: str,
        html_body: str,
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None
    ) -> bool:
        """
        Dispatches an email. In development/staging, logs the payload.
        """
        logger.info(
            f"[EMAIL_DISPATCH] Sending email to: {recipient_email} | Subject: '{subject}'"
            + (f" | Attachment: {attachment_filename}" if attachment_filename else "")
        )
        # Production integration hooks (e.g. boto3 ses or sendgrid client) go here.
        return True

    @classmethod
    async def send_security_alert_new_device(
        cls,
        recipient_email: str,
        phone_number: str,
        new_device_id: str,
        cooldown_hours: int = 48
    ):
        """
        Out-of-band security alert when an account is accessed from a foreign device.
        """
        subject = "URGENT SECURITY ALERT: New Device Login & Security Cooldown Active"
        body = f"""
        <h2>Microbond Security Notification</h2>
        <p>Your account (Phone: <strong>{phone_number}</strong>) was just logged into from an unrecognized device.</p>
        <p><strong>Device ID:</strong> <code>{new_device_id}</code></p>
        <div style="background: #fff3cd; padding: 12px; border-left: 4px solid #ffeeba; margin: 15px 0;">
            <p><strong>Defensive Action Taken:</strong> A <strong>{cooldown_hours}-Hour Security Cooldown</strong> has been automatically enabled. All withdrawals and payout claims are locked.</p>
            <p>Your account KYC trust state has been set to <strong>RE_VERIFICATION_REQUIRED</strong> to prevent unauthorized asset draining.</p>
        </div>
        <p>If this was NOT you (e.g. unauthorized SIM-swap), click below to immediately freeze all transactions:</p>
        <p><a href="https://app.microbond.io/security/freeze-account" style="background: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">Freeze Account Immediately</a></p>
        """
        return await cls.send_email(recipient_email, subject, body)

    @classmethod
    async def send_kyc_rejection_guidance(
        cls,
        recipient_email: str,
        rejection_reason: str,
        guidance_notes: str
    ):
        """
        Actionable KYC correction guidance email with deep links to re-verify.
        """
        subject = "Action Required: Update Your Microbond Identity Verification"
        body = f"""
        <h2>Identity Verification Needs Attention</h2>
        <p>We were unable to approve your recent identity verification submission.</p>
        <p><strong>Reason:</strong> {rejection_reason}</p>
        <p><strong>How to fix this:</strong> {guidance_notes}</p>
        <p>Please open the Microbond app to retake your document photo or complete the liveness selfie.</p>
        <p><a href="microbond://kyc/reverify" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">Update Verification in App</a></p>
        """
        return await cls.send_email(recipient_email, subject, body)

    @classmethod
    async def send_audit_report(
        cls,
        recipient_email: str,
        group_title: str,
        file_format: str,
        file_bytes: bytes
    ):
        """
        Dispatches formal group audit ledger / regulatory financial report.
        """
        subject = f"Audit Report & Financial Ledger: {group_title}"
        filename = f"{group_title.replace(' ', '_')}_Audit_Ledger.{file_format.lower()}"
        body = f"""
        <h2>Group Financial Audit Report</h2>
        <p>Attached is the official compiled ledger and balance sheet for <strong>{group_title}</strong>.</p>
        <p>This statement includes all double-entry ledger journals, member contribution records, and escrow states.</p>
        """
        return await cls.send_email(
            recipient_email=recipient_email,
            subject=subject,
            html_body=body,
            attachment_bytes=file_bytes,
            attachment_filename=filename
        )
