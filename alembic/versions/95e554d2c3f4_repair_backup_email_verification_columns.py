"""Ensure backup email verification columns exist on deployed databases.

Revision ID: 95e554d2c3f4
Revises: f10d61a2b3c4
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op


revision: str = "95e554d2c3f4"
down_revision: Union[str, Sequence[str], None] = "f10d61a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE usersecurityemail "
        "ADD COLUMN IF NOT EXISTS verification_token VARCHAR"
    )
    op.execute(
        "ALTER TABLE usersecurityemail "
        "ADD COLUMN IF NOT EXISTS verification_expires_at BIGINT"
    )


def downgrade() -> None:
    pass
