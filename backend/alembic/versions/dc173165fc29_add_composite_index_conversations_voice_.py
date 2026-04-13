"""add_composite_index_conversations_voice_session

Revision ID: dc173165fc29
Revises: 3dac90beeb35
Create Date: 2025-10-27 20:08:01.586339

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc173165fc29'
down_revision: Union[str, Sequence[str], None] = '3dac90beeb35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create composite index for voice session conversation lookups
    # This query runs on EVERY voice session initialization:
    # WHERE persona_id = X AND session_id = Y AND conversation_type = 'voice'
    op.create_index(
        'idx_conversations_voice_session',
        'conversations',
        ['persona_id', 'session_id', 'conversation_type'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the composite index
    op.drop_index('idx_conversations_voice_session', table_name='conversations')
