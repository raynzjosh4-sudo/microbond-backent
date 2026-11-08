"""Add group scope to inbox notifications.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-11-08 15:35:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification",
        sa.Column("group_id", sa.String(length=200), nullable=True),
    )
    op.create_index("ix_notification_group_id", "notification", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_group_id", table_name="notification")
    op.drop_column("notification", "group_id")
