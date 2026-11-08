"""Add persistent user notification inbox and reply threads.

Revision ID: e4f5a6b7c8d9
Revises: d0e1f2a3b4c5
Create Date: 2026-11-08 15:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("preview", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=True),
        sa.Column("source_id", sa.String(length=200), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("can_reply", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("dedupe_key", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["user.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recipient_user_id",
            "dedupe_key",
            name="uq_notification_recipient_dedupe",
        ),
    )
    op.create_index(
        "ix_notification_recipient_created",
        "notification",
        ["recipient_user_id", "created_at"],
    )
    op.create_index(
        "ix_notification_recipient_read",
        "notification",
        ["recipient_user_id", "read_at"],
    )
    op.create_index(
        "ix_notification_source",
        "notification",
        ["source_type", "source_id"],
    )

    op.create_table(
        "notificationreply",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), nullable=False),
        sa.Column("parent_reply_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["notification.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sender_user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_reply_id"], ["notificationreply.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notificationreply_notification_created",
        "notificationreply",
        ["notification_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notificationreply_notification_created",
        table_name="notificationreply",
    )
    op.drop_table("notificationreply")
    op.drop_index("ix_notification_source", table_name="notification")
    op.drop_index("ix_notification_recipient_read", table_name="notification")
    op.drop_index("ix_notification_recipient_created", table_name="notification")
    op.drop_table("notification")
