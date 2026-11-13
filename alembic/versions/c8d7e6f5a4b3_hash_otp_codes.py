"""Store OTPs as keyed hashes instead of plaintext codes.

Revision ID: c8d7e6f5a4b3
Revises: f5a6b7c8d9e0
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d7e6f5a4b3"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_context().as_sql:
        op.add_column(
            "otprecord",
            sa.Column("code_hash", sa.String(length=128), nullable=True),
        )
        op.add_column(
            "otprecord",
            sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        )
        op.execute('UPDATE "otprecord" SET "is_used" = TRUE, "code_hash" = \'\'')
        op.alter_column(
            "otprecord",
            "code_hash",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        op.drop_column("otprecord", "code")
        op.alter_column("otprecord", "attempts", server_default=None)
        for column in ("code_hash", "is_used", "created_at", "expires_at"):
            op.create_index(f"ix_otprecord_{column}", "otprecord", [column])
        return

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("otprecord"):
        return

    columns = {column["name"] for column in inspector.get_columns("otprecord")}
    if "code_hash" not in columns:
        op.add_column(
            "otprecord",
            sa.Column("code_hash", sa.String(length=128), nullable=True),
        )
    if "attempts" not in columns:
        op.add_column(
            "otprecord",
            sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        )

    if "code" in columns:
        op.execute('UPDATE "otprecord" SET "is_used" = TRUE, "code_hash" = \'\'')
        op.alter_column(
            "otprecord",
            "code_hash",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        op.drop_column("otprecord", "code")
    elif "code_hash" in columns:
        op.alter_column(
            "otprecord",
            "code_hash",
            existing_type=sa.String(length=128),
            nullable=False,
        )

    if "attempts" not in columns:
        op.alter_column("otprecord", "attempts", server_default=None)

    indexes = {index["name"] for index in inspector.get_indexes("otprecord")}
    for column in ("code_hash", "is_used", "created_at", "expires_at"):
        index_name = f"ix_otprecord_{column}"
        if index_name not in indexes:
            op.create_index(index_name, "otprecord", [column])


def downgrade() -> None:
    if op.get_context().as_sql:
        for column in ("expires_at", "created_at", "is_used", "code_hash"):
            op.drop_index(f"ix_otprecord_{column}", table_name="otprecord")
        op.add_column(
            "otprecord",
            sa.Column("code", sa.String(), nullable=True),
        )
        op.execute('UPDATE "otprecord" SET "code" = \'\'')
        op.alter_column(
            "otprecord",
            "code",
            existing_type=sa.String(),
            nullable=False,
        )
        op.drop_column("otprecord", "attempts")
        op.drop_column("otprecord", "code_hash")
        return

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("otprecord"):
        return

    columns = {column["name"] for column in inspector.get_columns("otprecord")}
    indexes = {index["name"] for index in inspector.get_indexes("otprecord")}
    for column in ("expires_at", "created_at", "is_used", "code_hash"):
        index_name = f"ix_otprecord_{column}"
        if index_name in indexes:
            op.drop_index(index_name, table_name="otprecord")

    if "code" not in columns:
        op.add_column(
            "otprecord",
            sa.Column("code", sa.String(), nullable=True),
        )
        op.execute('UPDATE "otprecord" SET "code" = \'\'')
        op.alter_column(
            "otprecord",
            "code",
            existing_type=sa.String(),
            nullable=False,
        )
    if "attempts" in columns:
        op.drop_column("otprecord", "attempts")
    if "code_hash" in columns:
        op.drop_column("otprecord", "code_hash")
