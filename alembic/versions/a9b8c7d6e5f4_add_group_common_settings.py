"""Add persistent common group settings.

Revision ID: a9b8c7d6e5f4
Revises: b8c0d3e4f5a6
Create Date: 2026-11-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, Sequence[str], None] = "b8c0d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "groupcommonsettings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.String(), nullable=False),
        sa.Column("allow_partial_payments", sa.Boolean(), nullable=False),
        sa.Column("minimum_partial_payment_amount", sa.Float(), nullable=True),
        sa.Column("minimum_kyc_tier", sa.Integer(), nullable=False),
        sa.Column("group_start_time", sa.BigInteger(), nullable=True),
        sa.Column("require_guarantor", sa.Boolean(), nullable=False),
        sa.Column("maximum_member_capacity", sa.Integer(), nullable=True),
        sa.Column("collection_frequency_days", sa.Integer(), nullable=True),
        sa.Column("grace_period_hours", sa.Integer(), nullable=False),
        sa.Column("late_payment_policy", sa.String(), nullable=False),
        sa.Column("payment_approval_threshold", sa.BigInteger(), nullable=True),
        sa.Column("allow_advance_payments", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["group.group_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id"),
    )
    op.create_index(
        op.f("ix_groupcommonsettings_group_id"),
        "groupcommonsettings",
        ["group_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_groupcommonsettings_group_id"), table_name="groupcommonsettings")
    op.drop_table("groupcommonsettings")
