"""Add backup email verification state columns.

Revision ID: f10d61a2b3c4
Revises: e3f4a5b6c7d8
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f10d61a2b3c4"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usersecurityemail",
        sa.Column("verification_token", sa.String(), nullable=True),
    )
    op.add_column(
        "usersecurityemail",
        sa.Column("verification_expires_at", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("usersecurityemail", "verification_expires_at")
    op.drop_column("usersecurityemail", "verification_token")
