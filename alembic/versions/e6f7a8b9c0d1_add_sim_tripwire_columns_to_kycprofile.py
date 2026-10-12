"""add sim tripwire columns to kycprofile

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-10-11 14:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('kycprofile',
        sa.Column('last_known_sim_registration_timestamp', sa.BigInteger(), nullable=True)
    )
    op.add_column('kycprofile',
        sa.Column('sim_swap_detected', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column('kycprofile',
        sa.Column('last_carrier_subscriber_id', sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('kycprofile', 'last_carrier_subscriber_id')
    op.drop_column('kycprofile', 'sim_swap_detected')
    op.drop_column('kycprofile', 'last_known_sim_registration_timestamp')
