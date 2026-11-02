def format_general_setting(field: str, old_value: object, new_value: object) -> tuple[str, str]:
    label = field.replace("_", " ")

    def format_value(item: object) -> str:
        if isinstance(item, bool):
            return "enabled" if item else "disabled"
        return "not set" if item is None else str(item)

    if isinstance(new_value, bool):
        value = "enabled" if new_value else "disabled"
        effect = f"The {label} rule is now {value}."
    elif new_value is None:
        effect = f"The {label} setting has been cleared."
    else:
        effect = f"This value will apply to future group activity."
    return (
        label,
        f"changed {label} from {format_value(old_value)} "
        f"to {format_value(new_value)}. {effect}",
    )
