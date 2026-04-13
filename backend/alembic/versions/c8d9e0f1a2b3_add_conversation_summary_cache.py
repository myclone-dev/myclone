"""add conversation summary cache columns

Revision ID: c8d9e0f1a2b3
Revises: 1bd75c734ca5
Create Date: 2025-11-20 03:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, Sequence[str], None] = '1bd75c734ca5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add summary cache columns to conversations table."""
    # Add summary cache columns
    op.add_column('conversations', sa.Column('ai_summary', sa.Text(), nullable=True))
    op.add_column('conversations', sa.Column('summary_metadata', JSONB, nullable=True))
    op.add_column('conversations', sa.Column('summary_generated_at', sa.DateTime(timezone=True), nullable=True))

    # Add index for fast lookup of cached summaries
    op.create_index(
        'idx_conversations_summary_generated',
        'conversations',
        ['id', 'summary_generated_at'],
        postgresql_where=sa.text('summary_generated_at IS NOT NULL')
    )


def downgrade() -> None:
    """Remove summary cache columns from conversations table."""
    # Drop index
    op.drop_index('idx_conversations_summary_generated', table_name='conversations')

    # Drop columns
    op.drop_column('conversations', 'summary_generated_at')
    op.drop_column('conversations', 'summary_metadata')
    op.drop_column('conversations', 'ai_summary')
