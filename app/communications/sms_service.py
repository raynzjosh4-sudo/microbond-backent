"""
sms_service facade — redirects to app.services.communication.sms and app.utils.phone
"""
from app.utils.phone.sanitize_uganda_phone import sanitize_uganda_phone
from app.services.communication.sms import (
    SMS_FEE_UGX,
    send_sms as _send_sms,
    send_real_otp_sms,
    send_overdue_reminder_sms,
    send_deposit_receipt_sms,
    send_sms_opt_in_consent_notice,
    send_payout_disbursed_sms,
)

__all__ = [
    "sanitize_uganda_phone",
    "SMS_FEE_UGX",
    "_send_sms",
    "send_real_otp_sms",
    "send_overdue_reminder_sms",
    "send_deposit_receipt_sms",
    "send_sms_opt_in_consent_notice",
    "send_payout_disbursed_sms",
]
