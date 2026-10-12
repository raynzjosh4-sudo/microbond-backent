"""add missing chat message columns to groupchatmessage

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-10-11 14:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add missing columns to groupchatmessage
    op.add_column('groupchatmessage',
        sa.Column('client_message_id', sa.String(), nullable=True)
    )
    op.add_column('groupchatmessage',
        sa.Column('media_type', sa.String(), nullable=True)
    )
    op.add_column('groupchatmessage',
        sa.Column('media_mime_type', sa.String(), nullable=True)
    )
    op.add_column('groupchatmessage',
        sa.Column('media_size_bytes', sa.Integer(), nullable=True)
    )
    op.add_column('groupchatmessage',
        sa.Column('media_duration_seconds', sa.Integer(), nullable=True)
    )
    op.add_column('groupchatmessage',
        sa.Column('status', sa.String(), nullable=False, server_default='SENT')
    )
    op.add_column('groupchatmessage',
        sa.Column('updated_at', sa.BigInteger(), nullable=True)
    )

    # 2. Make message_text nullable (for media-only messages)
    op.alter_column('groupchatmessage', 'message_text',
        existing_type=sa.VARCHAR(),
        nullable=True
    )

    # 3. Create indexes
    op.create_index(op.f('ix_groupchatmessage_client_message_id'), 'groupchatmessage', ['client_message_id'], unique=True)
    op.create_index('ix_chat_group_active_created', 'groupchatmessage', ['group_id', 'is_deleted', 'created_at'], unique=False)
    op.create_index(op.f('ix_groupchatmessage_created_at'), 'groupchatmessage', ['created_at'], unique=False)
    op.create_index(op.f('ix_groupchatmessage_updated_at'), 'groupchatmessage', ['updated_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_groupchatmessage_updated_at'), table_name='groupchatmessage')
    op.drop_index(op.f('ix_groupchatmessage_created_at'), table_name='groupchatmessage')
    op.drop_index('ix_chat_group_active_created', table_name='groupchatmessage')
    op.drop_index(op.f('ix_groupchatmessage_client_message_id'), table_name='groupchatmessage')

    op.alter_column('groupchatmessage', 'message_text',
        existing_type=sa.VARCHAR(),
        nullable=False
    )

    op.drop_column('groupchatmessage', 'updated_at')
    op.drop_column('groupchatmessage', 'status')
    op.drop_column('groupchatmessage', 'media_duration_seconds')
    op.drop_column('groupchatmessage', 'media_size_bytes')
    op.drop_column('groupchatmessage', 'media_mime_type')
    op.drop_column('groupchatmessage', 'media_type')
    op.drop_column('groupchatmessage', 'client_message_id')
