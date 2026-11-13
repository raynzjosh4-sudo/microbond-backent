"""Enforce idempotency and uniqueness for the API's new workflow tables.

Revision ID: d2e3f4a5b6c7
Revises: c8d7e6f5a4b3
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c8d7e6f5a4b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UNIQUE_INDEXES = (
    ("uq_user_client_request_id", "command_idempotency", "user_id, client_request_id", None),
    ("uq_rotating_cycle_group_number", "rotating_cycle", "group_id, cycle_number", None),
    (
        "uq_rotating_collection_cycle_user_date",
        "rotating_daily_collection",
        "cycle_id, user_id, collection_date",
        None,
    ),
    ("uq_rotating_payout_cycle", "rotating_payout", "cycle_id", None),
    (
        "uq_rotating_recipient_position",
        "rotating_payout_recipient",
        "payout_id, turn_position",
        None,
    ),
    (
        "uq_rotating_recipient_user",
        "rotating_payout_recipient",
        "payout_id, user_id",
        None,
    ),
    (
        "uq_payment_webhook_provider_event",
        "payment_webhook_event",
        "provider_name, provider_event_id",
        None,
    ),
    (
        "uq_backend_job_idempotency",
        "backend_job_execution",
        "job_type, idempotency_key",
        None,
    ),
    (
        "uq_active_group_role_grant",
        "group_role_grant",
        "group_id, user_id, role_code",
        "status = 'ACTIVE'",
    ),
    (
        "uq_active_group_permission_grant",
        "group_permission_grant",
        "group_id, user_id, permission_code",
        "status = 'ACTIVE'",
    ),
)


def upgrade() -> None:
    for name, table, columns, predicate in UNIQUE_INDEXES:
        where = f" WHERE {predicate}" if predicate else ""
        op.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {name} "
            f"ON {table} ({columns}){where}"
        )


def downgrade() -> None:
    for name, _, _, _ in reversed(UNIQUE_INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {name}")
