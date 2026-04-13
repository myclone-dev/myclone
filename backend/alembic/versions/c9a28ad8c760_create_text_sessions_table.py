"""create_text_sessions_table

Revision ID: c9a28ad8c760
Revises: fefd8f360446
Create Date: 2026-01-22 14:17:29.486641

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9a28ad8c760'
down_revision: Union[str, Sequence[str], None] = 'fefd8f360446'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create text_sessions table for text-only chat tracking
    op.create_table(
        'text_sessions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('persona_id', sa.UUID(), nullable=False),
        sa.Column('persona_owner_id', sa.UUID(), nullable=False, comment='User who owns the persona (gets charged)'),
        sa.Column('room_name', sa.String(255), nullable=False, comment='LiveKit room name'),
        sa.Column('message_count', sa.Integer(), server_default='0', nullable=False, comment='Total messages sent in this session'),
        sa.Column('session_token', sa.String(255), nullable=True, comment='User session token for linking to user_sessions'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True, comment='When session ended (NULL = active)'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['persona_owner_id'], ['users.id'], ondelete='CASCADE'),
        comment='Text chat session tracking (separate from voice_sessions)'
    )

    # Create indexes for performance
    op.create_index('idx_text_sessions_persona_id', 'text_sessions', ['persona_id'])
    op.create_index('idx_text_sessions_owner_id', 'text_sessions', ['persona_owner_id'])
    op.create_index('idx_text_sessions_room_name', 'text_sessions', ['room_name'])
    op.create_index('idx_text_sessions_started_at', 'text_sessions', ['started_at'])
    op.create_index('idx_text_sessions_active', 'text_sessions', ['ended_at'], postgresql_where=sa.text('ended_at IS NULL'))


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_text_sessions_active', 'text_sessions')
    op.drop_index('idx_text_sessions_started_at', 'text_sessions')
    op.drop_index('idx_text_sessions_room_name', 'text_sessions')
    op.drop_index('idx_text_sessions_owner_id', 'text_sessions')
    op.drop_index('idx_text_sessions_persona_id', 'text_sessions')

    # Drop table
    op.drop_table('text_sessions')
