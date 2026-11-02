def format_profile_setting(field: str, old_value: object, new_value: object) -> tuple[str, str]:
    if field == "name":
        return "group name", f"changed the group name from “{old_value}” to “{new_value}”."
    if field == "description":
        old_state = "set" if old_value else "empty"
        new_state = "set" if new_value else "empty"
        return "group description", f"changed the group description from {old_state} to {new_state}."
    if field == "group_image_url":
        old_state = "set" if old_value else "not set"
        new_state = "set" if new_value else "removed"
        return "group icon", f"changed the group icon from {old_state} to {new_state}."
    return field.replace("_", " "), f"updated {field.replace('_', ' ')}."
