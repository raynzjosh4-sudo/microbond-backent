from sqlmodel import Session, select

from app.models.group.report import GroupReportSectionVisibility

PAYOUT_GROUP_TYPES = {"MERRY_GO_ROUND"}


REPORT_SECTION_CATALOG = (
    {
        "key": "week_summary",
        "label": "Week summary",
        "description": "Totals, success rate, and key highlights.",
        "fields": ("report_period", "days_analyzed", "week_totals"),
    },
    {
        "key": "daily_records",
        "label": "Daily records",
        "description": "Daily savings and deposit records.",
        "fields": ("daily_saving", "deposit_status"),
    },
    {
        "key": "member_balances",
        "label": "Member balances",
        "description": "Member balance totals and changes.",
        "fields": ("balance_counts", "member_stats"),
    },
    {
        "key": "members_who_saved",
        "label": "Members who saved",
        "description": "Members who made a contribution during the period.",
        "fields": ("members_who_saved",),
    },
    {
        "key": "members_who_missed",
        "label": "Members who missed",
        "description": "Members who missed a scheduled contribution.",
        "fields": ("members_who_missed",),
    },
    {
        "key": "payout_rotation",
        "label": "Payout rotation",
        "description": "Completed and upcoming payout rotation.",
        "fields": ("payout_rotation",),
        "group_types": PAYOUT_GROUP_TYPES,
    },
    {
        "key": "group_activity",
        "label": "Group activity",
        "description": "Group activity and membership changes.",
        "fields": ("activity", "members"),
    },
    {
        "key": "contribution_history",
        "label": "Contribution history",
        "description": "Contribution obligations and payment history.",
        "fields": ("contribution_history",),
    },
    {
        "key": "all_members",
        "label": "All members",
        "description": "The active members included in this report.",
        "fields": ("all_members",),
    },
)

REPORT_SECTION_KEYS = tuple(section["key"] for section in REPORT_SECTION_CATALOG)
REPORT_SECTION_BY_KEY = {section["key"]: section for section in REPORT_SECTION_CATALOG}
REPORT_DETAIL_VISIBILITY_FIELDS = {
    "vis_report_expected_revenue": "vis_report_expected_revenue",
    "vis_report_actual_collection": "vis_report_actual_collection",
    "vis_report_deficit": "vis_report_deficit",
    "vis_report_reserve_fund": "vis_report_reserve_fund",
    "vis_report_escrow_holds": "vis_report_escrow_holds",
}


def load_report_section_visibility(session: Session, group_id: str) -> dict[str, bool]:
    rows = session.exec(
        select(GroupReportSectionVisibility).where(
            GroupReportSectionVisibility.group_id == group_id
        )
    ).all()
    saved = {row.section_key: row.visible_to_members for row in rows}
    missing_keys = set(REPORT_SECTION_KEYS) - set(saved)
    if missing_keys:
        session.add_all(
            GroupReportSectionVisibility(
                group_id=group_id,
                section_key=key,
                visible_to_members=False,
            )
            for key in missing_keys
        )
        session.commit()
    return {key: bool(saved.get(key, False)) for key in REPORT_SECTION_KEYS}


def available_report_sections(
    group_type: str,
    viewer_role: str,
    visibility: dict[str, bool],
) -> list[dict[str, str]]:
    is_admin = viewer_role == "ADMIN"
    return [
        {
            "key": section["key"],
            "label": section["label"],
            "description": section["description"],
        }
        for section in REPORT_SECTION_CATALOG
        if (
            not section.get("group_types") or group_type in section["group_types"]
        )
        and (is_admin or visibility.get(section["key"], False))
    ]


def report_detail_visibility(settings) -> dict[str, bool]:
    return {
        key: bool(getattr(settings, field_name))
        for key, field_name in REPORT_DETAIL_VISIBILITY_FIELDS.items()
    }