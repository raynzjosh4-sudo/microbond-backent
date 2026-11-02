import logging
import uuid
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlmodel import select

from app.api.routes.group.settings.announcements.formatters import (
    format_access_setting,
    format_common_setting,
    format_communication_setting,
    format_financial_setting,
    format_general_setting,
    format_profile_setting,
)
from app.api.routes.group.chat.messages.helpers.messages_helpers import (
    publish_saved_system_message_sync,
)
from app.models.group.chat import GroupChatMessage
from app.models.group.core.group import Group
from app.models.group.settings import GroupCommunicationSettings, GroupCommonSettings

logger = logging.getLogger(__name__)

IGNORED_FIELDS = {
    "id",
    "group_id",
    "created_at",
    "updated_at",
    "member_count",
    "total_balance",
    "current_balance",
    "current_cycle",
    "current_round",
}
FIELD_ALIASES = {
    "max_members": "maximum_member_capacity",
    "require_guarantors": "require_guarantor",
    "allow_advance_deposits": "allow_advance_payments",
    "arrears_policy": "late_payment_policy",
}


def _is_trackable(instance: object) -> bool:
    model = type(instance)
    return (
        model.__module__.startswith("app.models.group")
        and model.__name__ not in {"GroupReportSectionVisibility", "GroupFinancialReport"}
        and ".chat." not in model.__module__
        and hasattr(instance, "group_id")
    )


def _setting_default(instance: object, field: str) -> Any:
    model_field = getattr(type(instance), "model_fields", {}).get(field)
    if model_field is not None:
        if model_field.default_factory is not None:
            try:
                return model_field.default_factory()
            except TypeError:
                return None
        if model_field.default is not None:
            return model_field.default
    return None


def _changes_for_instance(instance: object, is_new: bool) -> list[tuple[str, Any, Any]]:
    state = inspect(instance)
    changes = []
    for field in state.mapper.column_attrs.keys():
        if field in IGNORED_FIELDS:
            continue
        history = state.attrs[field].history
        if is_new:
            old_value = _setting_default(instance, field)
            new_value = getattr(instance, field, None)
            if old_value == new_value:
                continue
        elif history.has_changes():
            old_value = history.deleted[0] if history.deleted else None
            new_value = getattr(instance, field, None)
        else:
            continue
        if old_value != new_value:
            changes.append((field, old_value, new_value))
    return changes


def _category(model_name: str, field: str) -> str:
    if model_name == GroupCommonSettings.__name__:
        return "COMMON"
    if model_name == Group.__name__:
        return "PROFILE"
    if field.startswith("vis_") or "visibility" in field:
        return "PRIVACY"
    if any(token in field for token in ("announce", "broadcast", "notify", "post_", "send_")):
        return "COMMUNICATION"
    if any(token in field for token in ("balance", "contact", "discoverability", "visibility")):
        return "PRIVACY"
    if any(token in field for token in ("permission", "member", "invite", "approval", "guarantor")):
        return "PERMISSIONS"
    if any(token in field for token in ("payment", "fee", "grace", "arrears", "deposit", "collection")):
        return "FINANCIAL"
    return "GENERAL"


def _format_setting(model_name: str, field: str, old_value: Any, new_value: Any) -> tuple[str, str]:
    category = _category(model_name, field)
    if category == "PROFILE":
        return format_profile_setting(field, old_value, new_value)
    if category == "COMMUNICATION":
        return format_communication_setting(field, old_value, new_value)
    if category == "FINANCIAL":
        return format_financial_setting(field, old_value, new_value)
    if category in {"PERMISSIONS", "PRIVACY"}:
        return format_access_setting(field, old_value, new_value)
    return format_general_setting(field, old_value, new_value)


def _announcements_enabled(session: SQLAlchemySession, group_id: str) -> bool:
    for instance in (*session.new, *session.dirty):
        if (
            isinstance(instance, GroupCommunicationSettings)
            and str(instance.group_id) == group_id
        ):
            return bool(instance.announce_system_events)

    statement = select(GroupCommunicationSettings.announce_system_events).where(
        GroupCommunicationSettings.group_id == group_id
    )
    enabled = session.connection().execute(statement).scalar_one_or_none()
    return enabled is not False


def _capture_changes(
    session: SQLAlchemySession,
    flush_context: Any,
    instances: Any,
) -> None:
    del flush_context, instances
    context = session.info.get("settings_announcement_context")
    if (
        not context
        or context.get("method") not in {"POST", "PUT", "PATCH", "DELETE"}
        or (
            "/settings" not in context.get("path", "")
            and not context.get("path", "").endswith("/avatar")
        )
        or session.info.get("settings_announcement_skip_tracker")
    ):
        return

    pending = session.info.setdefault("settings_changes", {})
    candidates = [
        *((item, True) for item in session.new),
        *((item, False) for item in session.dirty),
    ]
    for instance, is_new in candidates:
        if not _is_trackable(instance) or isinstance(instance, GroupCommonSettings):
            continue
        group_id = getattr(instance, "group_id", None)
        if not group_id:
            continue
        for field, old_value, new_value in _changes_for_instance(instance, is_new):
            key = (str(group_id), type(instance).__name__, field)
            if key in pending:
                pending[key] = (pending[key][0], new_value)
            else:
                pending[key] = (old_value, new_value)


def _create_announcements(
    session: SQLAlchemySession,
    flush_context: Any,
    instances: Any,
) -> None:
    del flush_context, instances
    if session.info.get("settings_announcement_processing"):
        return
    changes = session.info.pop("settings_changes", {})
    common_changes = session.info.pop("settings_announcement_common_changes", {})
    context = session.info.get("settings_announcement_context")
    if not context:
        return

    group_id = context.get("group_id")
    if group_id:
        for field, values in common_changes.items():
            changes[(str(group_id), GroupCommonSettings.__name__, field)] = values
    if not changes:
        return

    session.info["settings_announcement_processing"] = True
    try:
        _persist_announcements(
            session,
            changes,
            context,
            session.info.pop("settings_announcement_common_settings", None),
        )
    finally:
        session.info.pop("settings_announcement_processing", None)


def _persist_announcements(
    session: SQLAlchemySession,
    changes: dict,
    context: dict,
    common_settings: GroupCommonSettings | None,
) -> None:
    changed_by_group: dict[str, list[tuple[str, str, Any, Any]]] = {}
    seen = set()
    for (group_id, model_name, field), (old_value, new_value) in changes.items():
        canonical_field = FIELD_ALIASES.get(field, field)
        dedupe_key = (group_id, canonical_field, repr(new_value))
        if dedupe_key in seen or old_value == new_value:
            continue
        seen.add(dedupe_key)
        changed_by_group.setdefault(group_id, []).append(
            (model_name, field, old_value, new_value)
        )

    for group_id, changed_settings in changed_by_group.items():
        if not _announcements_enabled(session, group_id):
            continue

        actor_id = context["actor_id"]
        actor_name = context.get("actor_name") or "Group Admin"
        for model_name, field, old_value, new_value in changed_settings:
            if model_name == GroupCommonSettings.__name__ and common_settings:
                label, details = format_common_setting(
                    field, old_value, new_value, common_settings
                )
            else:
                label, details = _format_setting(
                    model_name, field, old_value, new_value
                )
            image_url = new_value if field == "group_image_url" and new_value else None
            message = GroupChatMessage(
                client_message_id=str(uuid.uuid4()),
                group_id=group_id,
                sender_id=actor_id,
                message_type="SYSTEM_EVENT",
                message_text=f"⚙️ {actor_name} {details}",
                media_url=image_url,
                media_type="IMAGE" if image_url else None,
                attachments=[
                    {
                        "category": "SETTINGS_UPDATE",
                        "setting_type": _category(model_name, field),
                        "setting": field,
                        "setting_label": label,
                        "admin_id": actor_id,
                        "admin_name": actor_name,
                        "changes_count": 1,
                    }
                ],
                status="SENT",
            )
            session.add(message)
            session.info.setdefault("settings_announcement_messages", []).append(message)
        session.info["settings_announcement_pending"] = True


def register_settings_announcement_events() -> None:
    if event.contains(SQLAlchemySession, "before_flush", _capture_changes):
        return
    event.listen(SQLAlchemySession, "before_flush", _capture_changes)
    event.listen(SQLAlchemySession, "before_flush", _create_announcements)
    event.listen(SQLAlchemySession, "after_commit", _publish_announcements)
    event.listen(SQLAlchemySession, "after_rollback", _discard_announcements)


def _publish_announcements(session: SQLAlchemySession) -> None:
    messages = session.info.pop("settings_announcement_messages", [])
    for message in messages:
        try:
            publish_saved_system_message_sync(message)
        except Exception:
            logger.exception("Could not publish group settings announcement")


def _discard_announcements(session: SQLAlchemySession) -> None:
    session.info.pop("settings_changes", None)
    session.info.pop("settings_announcement_messages", None)
    session.info.pop("settings_announcement_pending", None)
