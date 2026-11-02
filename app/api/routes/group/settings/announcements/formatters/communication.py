COMMUNICATION_LABELS = {
    "announce_system_events": "system event announcements",
    "broadcast_individual_deposit_receipts": "deposit receipt announcements",
    "announce_payout_updates": "payout announcements",
    "share_financial_snapshots": "financial snapshots",
    "send_daily_group_summaries": "daily group summaries",
    "post_weekly_financial_reports": "weekly financial reports",
}


def format_communication_setting(
    field: str,
    old_value: object,
    new_value: object,
) -> tuple[str, str]:
    label = COMMUNICATION_LABELS.get(field, field.replace("_", " "))

    def value(value: object) -> str:
        if isinstance(value, bool):
            return "enabled" if value else "disabled"
        return "not set" if value is None else str(value)

    if field == "announce_system_events":
        effect = (
            "Future group setting changes will be announced in this chat."
            if new_value
            else "Future group setting changes will not be announced in this chat."
        )
    else:
        effect = f"The group will use this {label} setting for future activity."
    return label, f"changed {label} from {value(old_value)} to {value(new_value)}. {effect}"
