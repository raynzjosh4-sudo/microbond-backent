from app.models.group.settings import GroupCommonSettings

SETTING_LABELS = {
    "allow_partial_payments": "partial payments",
    "minimum_partial_payment_amount": "minimum partial payment",
    "minimum_kyc_tier": "minimum KYC tier",
    "group_start_time": "group start time",
    "require_guarantor": "guarantor requirement",
    "maximum_member_capacity": "maximum member capacity",
    "collection_frequency_days": "collection frequency",
    "grace_period_hours": "grace period",
    "late_payment_policy": "late payment policy",
    "payment_approval_threshold": "payment approval threshold",
    "allow_advance_payments": "advance payments",
}


def _format_setting_value(field: str, value: object) -> str:
    if field in {
        "allow_partial_payments",
        "require_guarantor",
        "allow_advance_payments",
    }:
        return "Enabled" if value else "Disabled"
    if value is None:
        return "Not set"
    if field in {"minimum_partial_payment_amount", "payment_approval_threshold"}:
        return f"UGX {value:,.0f}"
    if field == "grace_period_hours":
        return f"{value} hours"
    if field == "maximum_member_capacity":
        return f"{value} members"
    if field == "collection_frequency_days":
        return "Daily/flexible" if value == 0 else f"Every {value} days"
    if field == "group_start_time":
        return f"{value} (Unix milliseconds)"
    return str(value)


def _setting_effect(field: str, settings: GroupCommonSettings) -> str:
    if field == "allow_partial_payments":
        if settings.allow_partial_payments:
            amount = _format_setting_value(
                "minimum_partial_payment_amount",
                settings.minimum_partial_payment_amount,
            )
            return (
                f"Members can pay in installments, with each installment "
                f"at least {amount}."
            )
        return "Members must pay the full contribution in one payment."
    if field == "minimum_partial_payment_amount":
        return "Partial payments below this amount will not be accepted."
    if field == "minimum_kyc_tier":
        return "Members must meet this KYC tier to satisfy the group's KYC requirement."
    if field == "group_start_time":
        return "The group schedule will use this start time."
    if field == "require_guarantor":
        if settings.require_guarantor:
            return "Members must have a guarantor to satisfy the group's participation rules."
        return "A guarantor is no longer required by this group setting."
    if field == "maximum_member_capacity":
        return "The group will not accept members beyond this capacity."
    if field == "collection_frequency_days":
        if settings.collection_frequency_days == 0:
            return "Contributions can be collected daily or flexibly."
        return (
            "Contributions will follow this collection interval "
            f"({settings.collection_frequency_days} days)."
        )
    if field == "grace_period_hours":
        return f"Members have {settings.grace_period_hours} hours after the deadline before the grace period ends."
    if field == "late_payment_policy":
        return f"This policy will be applied when a member misses a payment: {settings.late_payment_policy}."
    if field == "payment_approval_threshold":
        threshold = _format_setting_value(
            field, settings.payment_approval_threshold
        )
        return (
            "Payments above this amount are subject to the group's approval "
            f"process ({threshold})."
        )
    if field == "allow_advance_payments":
        if settings.allow_advance_payments:
            return "Members can pay ahead toward upcoming contributions."
        return "Members cannot pay ahead toward upcoming contributions."
    return "The updated setting now applies to this group."


def format_common_setting(
    field: str,
    old_value: object,
    new_value: object,
    settings: GroupCommonSettings,
) -> tuple[str, str]:
    label = SETTING_LABELS[field]
    details = (
        f"changed {label} from {_format_setting_value(field, old_value)} "
        f"to {_format_setting_value(field, new_value)}. "
        f"{_setting_effect(field, settings)}"
    )
    return label, details
