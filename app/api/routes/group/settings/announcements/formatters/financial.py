FINANCIAL_LABELS = {
    "grace_period_hours": "grace period",
    "arrears_policy": "late payment policy",
    "late_fee_amount": "late fee amount",
    "enable_late_fees": "late fees",
    "payment_approval_threshold": "payment approval threshold",
    "minimum_partial_payment_amount": "minimum partial payment",
}


def format_financial_setting(field: str, old_value: object, new_value: object) -> tuple[str, str]:
    label = FINANCIAL_LABELS.get(field, field.replace("_", " "))

    def value(item: object) -> str:
        if isinstance(item, bool):
            return "enabled" if item else "disabled"
        if item is None:
            return "not set"
        if field in {"late_fee_amount", "payment_approval_threshold", "minimum_partial_payment_amount"}:
            return f"UGX {item:,.0f}"
        if field == "grace_period_hours":
            return f"{item} hours"
        return str(item)

    effect = (
        "This policy will apply to future group payments."
        if field in {"arrears_policy", "grace_period_hours"}
        else "This rule will apply to future group payments."
    )
    return label, f"changed {label} from {value(old_value)} to {value(new_value)}. {effect}"
