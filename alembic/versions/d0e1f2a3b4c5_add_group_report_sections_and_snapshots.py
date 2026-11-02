"""add per-group report section visibility and financial report snapshots

Revision ID: d0e1f2a3b4c5
Revises: a9b8c7d6e5f4
Create Date: 2026-11-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REPORT_SECTION_KEYS = (
    "week_summary",
    "daily_records",
    "member_balances",
    "members_who_saved",
    "members_who_missed",
    "payout_rotation",
    "group_activity",
    "contribution_history",
    "all_members",
)


def upgrade() -> None:
    op.create_table(
        "groupreportsectionvisibility",
        sa.Column("group_id", sa.String(), nullable=False),
        sa.Column("section_key", sa.String(), nullable=False),
        sa.Column(
            "visible_to_members",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["group_id"], ["group.group_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("group_id", "section_key"),
        sa.CheckConstraint(
            "section_key IN ("
            + ", ".join(repr(key) for key in REPORT_SECTION_KEYS)
            + ")",
            name="groupreportsectionvisibility_section_key_check",
        ),
    )
    op.create_index(
        "ix_groupreportsectionvisibility_group_id",
        "groupreportsectionvisibility",
        ["group_id"],
    )

    op.create_table(
        "groupfinancialreport",
        sa.Column("report_id", sa.String(), nullable=False),
        sa.Column("group_id", sa.String(), nullable=False),
        sa.Column("requester_user_id", sa.Uuid(), nullable=False),
        sa.Column("period_type", sa.String(), nullable=False),
        sa.Column("selected_date", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("included_sections", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["group_id"], ["group.group_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("report_id"),
    )
    op.create_index("ix_groupfinancialreport_group_id", "groupfinancialreport", ["group_id"])
    op.create_index(
        "ix_groupfinancialreport_requester_user_id",
        "groupfinancialreport",
        ["requester_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_groupfinancialreport_requester_user_id", table_name="groupfinancialreport")
    op.drop_index("ix_groupfinancialreport_group_id", table_name="groupfinancialreport")
    op.drop_table("groupfinancialreport")
    op.drop_index(
        "ix_groupreportsectionvisibility_group_id",
        table_name="groupreportsectionvisibility",
    )
    op.drop_table("groupreportsectionvisibility")