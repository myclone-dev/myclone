"""Add platform and model columns to voice_clones table

Revision ID: ca5c192f3e3e
Revises: d7660f64a64b
Create Date: 2025-12-06 02:17:17.689042

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ca5c192f3e3e'
down_revision: Union[str, Sequence[str], None] = 'd7660f64a64b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add platform and model columns to voice_clones table."""
    
    # Add platform column with default 'elevenlabs'
    op.add_column('voice_clones', 
        sa.Column('platform', sa.Text(), nullable=False, server_default='elevenlabs',
                  comment="Voice platform used: elevenlabs, playht, cartesia, or custom")
    )
    
    # Add model column (nullable by default)
    op.add_column('voice_clones',
        sa.Column('model', sa.Text(), nullable=True,
                  comment="Model identifier for the voice clone")
    )
    
    # Update existing rows to have 'elevenlabs' as platform value
    # (This is redundant with server_default but explicit for clarity)
    op.execute("UPDATE voice_clones SET platform = 'elevenlabs' WHERE platform IS NULL OR platform = ''")
    
    # Add check constraint for platform values
    op.create_check_constraint(
        'ck_voice_clones_platform',
        'voice_clones',
        "platform IN ('elevenlabs', 'playht', 'cartesia', 'custom')"
    )
    
    # Create index on platform for faster filtering
    op.create_index('idx_voice_clones_platform', 'voice_clones', ['platform'], unique=False)


def downgrade() -> None:
    """Remove platform and model columns from voice_clones table."""
    
    # Drop index
    op.drop_index('idx_voice_clones_platform', table_name='voice_clones')
    
    # Drop check constraint
    op.drop_constraint('ck_voice_clones_platform', 'voice_clones', type_='check')
    
    # Drop columns
    op.drop_column('voice_clones', 'model')
    op.drop_column('voice_clones', 'platform')

