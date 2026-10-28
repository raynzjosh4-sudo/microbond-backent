"""Add shared group start date and goal-savings configuration.

Revision ID: b8c0d3e4f5a6
Revises: 70f802cd6a0e, e2f3a4b5c6d7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c0d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = (
    "70f802cd6a0e",
    "e2f3a4b5c6d7",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    group_columns = {column["name"] for column in inspector.get_columns("group")}
    if "start_date" not in group_columns:
        op.add_column("group", sa.Column("start_date", sa.BigInteger(), nullable=True))
        op.execute('UPDATE "group" SET start_date = created_at WHERE start_date IS NULL')
        op.alter_column("group", "start_date", nullable=False)

    inspector = sa.inspect(bind)
    if "groupgovernancesettings" in inspector.get_table_names():
        governance_columns = {
            column["name"]
            for column in inspector.get_columns("groupgovernancesettings")
        }
        if "minimum_kyc_tier" not in governance_columns:
            op.add_column(
                "groupgovernancesettings",
                sa.Column(
                    "minimum_kyc_tier",
                    sa.Integer(),
                    nullable=False,
                    server_default="1",
                ),
            )

    inspector = sa.inspect(bind)
    if "targetsavingsgroupdetails" not in inspector.get_table_names():
        return

    target_columns = {
        column["name"]
        for column in inspector.get_columns("targetsavingsgroupdetails")
    }
    new_flags = {
        "allow_target_amount": sa.Boolean(),
        "allow_target_date": sa.Boolean(),
        "allow_contribution_schedule": sa.Boolean(),
        "allow_collection_frequency": sa.Boolean(),
        "allow_multi_payout": sa.Boolean(),
    }
    defaults = {
        "allow_target_amount": sa.text("false"),
        "allow_target_date": sa.text("false"),
        "allow_contribution_schedule": sa.text("false"),
        "allow_collection_frequency": sa.text("false"),
        "allow_multi_payout": sa.text("true"),
    }
    for column_name, column_type in new_flags.items():
        if column_name not in target_columns:
            op.add_column(
                "targetsavingsgroupdetails",
                sa.Column(
                    column_name,
                    column_type,
                    nullable=False,
                    server_default=defaults[column_name],
                ),
            )

    op.execute(
        """
        UPDATE targetsavingsgroupdetails
        SET allow_target_amount = (target_amount > 0),
            allow_target_date = (target_date IS NOT NULL AND target_date > 0),
            allow_contribution_schedule = (contribution_amount > 0),
            allow_collection_frequency = (collection_frequency_days > 0
                AND contribution_amount > 0)
        """
    )

    with op.batch_alter_table("targetsavingsgroupdetails") as batch:
        batch.alter_column("target_amount", existing_type=sa.BigInteger(), nullable=True)
        batch.alter_column("target_date", existing_type=sa.BigInteger(), nullable=True)

    proposal_exists = "targetsavingspayoutproposal" in inspector.get_table_names()
    if not proposal_exists:
        op.create_table(
            "targetsavingspayoutproposal",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("group_id", sa.String(), nullable=False),
            sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
            sa.Column("provider_name", sa.String(), nullable=False),
            sa.Column("account_type", sa.String(), nullable=False),
            sa.Column("account_number", sa.String(), nullable=False),
            sa.Column("account_name", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["group_id"], ["group.group_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_targetsavingspayoutproposal_group_id",
            "targetsavingspayoutproposal",
            ["group_id"],
        )

    inspector = sa.inspect(bind)
    if "targetsavingspayoutapproval" not in inspector.get_table_names():
        op.create_table(
            "targetsavingspayoutapproval",
            sa.Column("proposal_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("approved", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(
                ["proposal_id"],
                ["targetsavingspayoutproposal.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("proposal_id", "user_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "targetsavingspayoutapproval" in tables:
        op.drop_table("targetsavingspayoutapproval")
    if "targetsavingspayoutproposal" in tables:
        op.drop_index(
            "ix_targetsavingspayoutproposal_group_id",
            table_name="targetsavingspayoutproposal",
        )
        op.drop_table("targetsavingspayoutproposal")
    if "targetsavingsgroupdetails" in tables:
        op.execute(
            """
            UPDATE targetsavingsgroupdetails
            SET target_amount = COALESCE(target_amount, 0),
                target_date = COALESCE(target_date, 0)
            """
        )
        with op.batch_alter_table("targetsavingsgroupdetails") as batch:
            batch.alter_column("target_amount", existing_type=sa.BigInteger(), nullable=False)
            batch.alter_column("target_date", existing_type=sa.BigInteger(), nullable=False)
            for name in (
                "allow_target_amount",
                "allow_target_date",
                "allow_contribution_schedule",
                "allow_collection_frequency",
                "allow_multi_payout",
            ):
                batch.drop_column(name)
    if "groupgovernancesettings" in tables:
        governance_columns = {
            column["name"]
            for column in inspector.get_columns("groupgovernancesettings")
        }
        if "minimum_kyc_tier" in governance_columns:
            op.drop_column("groupgovernancesettings", "minimum_kyc_tier")
    if "group" in tables:
        op.drop_column("group", "start_date")
