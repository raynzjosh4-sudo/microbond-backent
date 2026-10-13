from .layout import (
    wrap as _wrap,
    get_year as _get_year,
    _BASE_STYLES,
    _ICON_URL,
    _CODE_HERO_URL,
    _STMT_HERO_URL,
    _SECURITY_HERO_URL,
    _PAYMENT_REMINDER_HERO_URL,
    _BRAND,
    _TEXT,
    _MUTED,
    _BORDER,
)
from .auth_verification_template import verification_code, otp_code
from .account_statement_template import account_statement
from .security_alerts_template import (
    security_alert_new_device,
    security_alert_email_takeover_attempt,
    security_email_unlinked_notification,
)
from .kyc_guidance_template import kyc_rejection_guidance
from .group_audit_template import audit_report
from .payment_reminder_template import build_overdue_reminder_email
from .deposit_receipt_template import build_deposit_receipt_email
from .payout_disbursed_template import build_payout_disbursed_email

__all__ = [
    "_wrap",
    "_get_year",
    "_BASE_STYLES",
    "_ICON_URL",
    "_CODE_HERO_URL",
    "_STMT_HERO_URL",
    "_SECURITY_HERO_URL",
    "_PAYMENT_REMINDER_HERO_URL",
    "_BRAND",
    "_TEXT",
    "_MUTED",
    "_BORDER",
    "verification_code",
    "otp_code",
    "account_statement",
    "security_alert_new_device",
    "security_alert_email_takeover_attempt",
    "security_email_unlinked_notification",
    "kyc_rejection_guidance",
    "audit_report",
    "build_overdue_reminder_email",
    "build_deposit_receipt_email",
    "build_payout_disbursed_email",
]
