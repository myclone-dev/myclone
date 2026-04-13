"""Add voice_clones table for ElevenLabs voice sample tracking

Revision ID: 6zze0hn3mbdo
Revises: f1g2h3i4j5k6
Create Date: 2025-10-18 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6zze0hn3mbdo'
down_revision: Union[str, Sequence[str], None] = 'f1g2h3i4j5k6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add voice_clones table."""

    # Create voice_clones table
    op.create_table('voice_clones',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('voice_id', sa.Text(), nullable=False, comment='ElevenLabs voice ID'),
        sa.Column('name', sa.Text(), nullable=False, comment='Voice clone name'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sample_files', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False, comment='Array of S3 paths and metadata for uploaded voice samples'),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False, comment='Voice clone settings (remove_background_noise, etc.)'),
        sa.Column('total_files', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_size_bytes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('voice_id', name='uq_voice_clones_voice_id'),
        comment='Voice clone samples uploaded to ElevenLabs with S3 storage paths for audit trail'
    )

    # Create indexes for voice_clones
    op.create_index('idx_voice_clones_user_id', 'voice_clones', ['user_id'], unique=False)
    op.create_index('idx_voice_clones_voice_id', 'voice_clones', ['voice_id'], unique=False)
    op.create_index('idx_voice_clones_created_at', 'voice_clones', ['created_at'], unique=False)


def downgrade() -> None:
    """Remove voice_clones table."""

    # Drop indexes
    op.drop_index('idx_voice_clones_created_at', table_name='voice_clones')
    op.drop_index('idx_voice_clones_voice_id', table_name='voice_clones')
    op.drop_index('idx_voice_clones_user_id', table_name='voice_clones')

    # Drop table
    op.drop_table('voice_clones')
