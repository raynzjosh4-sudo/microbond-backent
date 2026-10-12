"""add attachments json and media dimensions to groupchatmessage

Revision ID: 4230cd2451ea
Revises: 1b9a5b3175a6
Create Date: 2026-10-11 17:57:02.944812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '4230cd2451ea'
down_revision: Union[str, Sequence[str], None] = '1b9a5b3175a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('groupchatmessage',
        sa.Column('attachments', sa.JSON(), nullable=True)
    )
    op.add_column('groupchatmessage',
        sa.Column('media_width', sa.Integer(), nullable=True)
    )
    op.add_column('groupchatmessage',
        sa.Column('media_height', sa.Integer(), nullable=True)
    )
    op.add_column('groupchatmessage',
        sa.Column('aspect_ratio', sa.Float(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('groupchatmessage', 'aspect_ratio')
    op.drop_column('groupchatmessage', 'media_height')
    op.drop_column('groupchatmessage', 'media_width')
    op.drop_column('groupchatmessage', 'attachments')
