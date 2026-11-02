def format_access_setting(
    field: str,
    old_value: object,
    new_value: object,
) -> tuple[str, str]:
    labels = {
        "members_can_edit_settings": "member setting permissions",
        "members_can_send_messages": "member messaging permissions",
        "members_can_invite_via_link": "invite-link permissions",
        "admins_must_approve_new_members": "new-member approval",
        "requires_admin_approval": "new-member approval",
        "hide_total_group_balance": "group balance visibility",
        "hide_member_contact_info": "member contact visibility",
        "invite_only_discoverability": "group discoverability",
        "announce_system_events": "system event announcements",
        "vis_announce_system_events": "system event announcements",
        "vis_report_expected_revenue": "expected revenue in member reports",
        "vis_report_actual_collection": "actual collections in member reports",
        "vis_report_deficit": "deficit tracking in member reports",
        "vis_report_reserve_fund": "reserve fund status in member reports",
        "vis_report_escrow_holds": "escrow holds in member reports",
        "vis_member_total_savings": "member savings totals",
    }
    visibility_setting = field.startswith("vis_")
    setting_label = labels.get(
        field,
        field.removeprefix("vis_").replace("_", " "),
    )
    label = (
        f"{setting_label} member visibility"
        if visibility_setting and not field.startswith("vis_report_")
        else setting_label
    )

    def visibility_value(value: object) -> str:
        if value is None:
            return "not set"
        if isinstance(value, bool):
            return "shown" if value else "hidden"
        return str(value)

    def setting_value(value: object) -> str:
        if value is None:
            return "not set"
        if field == "invite_only_discoverability":
            return "invite-only" if value else "public"
        if isinstance(value, bool):
            return "enabled" if value else "disabled"
        return str(value)

    value_formatter = visibility_value if visibility_setting else setting_value
    effects = {
        "announce_system_events": (
            "Future group setting changes will be announced in this chat."
            if new_value
            else "Future group setting changes will not be announced in this chat."
        ),
        "hide_total_group_balance": (
            "The group balance is hidden from members."
            if new_value
            else "The group balance is visible to members."
        ),
        "hide_member_contact_info": (
            "Member contact details are hidden from other members."
            if new_value
            else "Member contact details are visible according to group access rules."
        ),
        "invite_only_discoverability": (
            "The group can only be discovered through an invitation."
            if new_value
            else "The group is discoverable according to its visibility settings."
        ),
        "vis_report_expected_revenue": (
            "Members can see expected revenue on the report card."
            if new_value
            else "Expected revenue is hidden from the member report card."
        ),
        "vis_report_actual_collection": (
            "Members can see actual collections on the report card."
            if new_value
            else "Actual collections are hidden from the member report card."
        ),
        "vis_report_deficit": (
            "Members can see deficit tracking on the report card."
            if new_value
            else "Deficit tracking is hidden from the member report card."
        ),
        "vis_report_reserve_fund": (
            "Members can see reserve fund status on the report card."
            if new_value
            else "Reserve fund status is hidden from the member report card."
        ),
        "vis_report_escrow_holds": (
            "Members can see escrow holds on the report card."
            if new_value
            else "Escrow holds are hidden from the member report card."
        ),
        "vis_member_total_savings": (
            "Members can see member savings totals."
            if new_value
            else "Member savings totals are hidden from members."
        ),
    }
    effect = effects.get(
        field,
        (
            f"The {setting_label} setting is now visible to members."
            if visibility_setting and new_value
            else f"The {setting_label} setting is now hidden from members."
            if visibility_setting
            else f"This permission is now {value_formatter(new_value)}."
        ),
    )
    return (
        label,
        f"changed {label} from {value_formatter(old_value)} "
        f"to {value_formatter(new_value)}. {effect}",
    )
