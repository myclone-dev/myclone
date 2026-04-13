"""merge_all_heads_and_add_youtube_videos_table

Revision ID: f1g2h3i4j5k6
Revises: 301ca550b0cc, 1ecf868eb955
Create Date: 2025-10-15 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1g2h3i4j5k6'
down_revision: Union[str, Sequence[str], None] = ('301ca550b0cc', '1ecf868eb955')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge all heads and add YouTube videos table."""

    # Create youtube_videos table
    op.create_table('youtube_videos',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('video_url', sa.Text(), nullable=False),
        sa.Column('thumbnail_url', sa.Text(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('view_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('channel_name', sa.Text(), nullable=True),
        sa.Column('channel_url', sa.Text(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_id', name='uq_youtube_videos_video_id'),
        comment='YouTube videos - raw data only, embeddings stored in content_chunks'
    )

    # Create indexes for youtube_videos
    op.create_index('idx_youtube_videos_user_id', 'youtube_videos', ['user_id'], unique=False)
    op.create_index('idx_youtube_videos_video_id', 'youtube_videos', ['video_id'], unique=False)
    op.create_index('idx_youtube_videos_published_at', 'youtube_videos', [sa.text('published_at DESC')], unique=False)

    # Add youtube_video_id column to scraping_jobs table
    op.add_column('scraping_jobs', sa.Column('youtube_video_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_scraping_jobs_youtube_video_id', 'scraping_jobs', 'youtube_videos', ['youtube_video_id'], ['id'], ondelete='SET NULL')

    # Update check constraints to include 'youtube' as valid source type
    op.drop_constraint('ck_persona_data_sources_valid_source_type', 'persona_data_sources', type_='check')
    op.create_check_constraint(
        'ck_persona_data_sources_valid_source_type',
        'persona_data_sources',
        "source_type IN ('linkedin', 'twitter', 'website', 'pdf', 'github', 'medium', 'youtube', 'document')"
    )

    op.drop_constraint('ck_scraping_jobs_valid_source_type', 'scraping_jobs', type_='check')
    op.create_check_constraint(
        'ck_scraping_jobs_valid_source_type',
        'scraping_jobs',
        "source_type IN ('linkedin', 'twitter', 'website', 'pdf', 'document', 'youtube')"
    )


def downgrade() -> None:
    """Remove YouTube videos table and revert related changes."""

    # Revert check constraints
    op.drop_constraint('ck_scraping_jobs_valid_source_type', 'scraping_jobs', type_='check')
    op.create_check_constraint(
        'ck_scraping_jobs_valid_source_type',
        'scraping_jobs',
        "source_type IN ('linkedin', 'twitter', 'website', 'pdf', 'document')"
    )

    op.drop_constraint('ck_persona_data_sources_valid_source_type', 'persona_data_sources', type_='check')
    op.create_check_constraint(
        'ck_persona_data_sources_valid_source_type',
        'persona_data_sources',
        "source_type IN ('linkedin', 'twitter', 'website', 'pdf', 'github', 'medium', 'document')"
    )

    # Remove youtube_video_id column from scraping_jobs
    op.drop_constraint('fk_scraping_jobs_youtube_video_id', 'scraping_jobs', type_='foreignkey')
    op.drop_column('scraping_jobs', 'youtube_video_id')

    # Drop youtube_videos table (indexes will be dropped automatically)
    op.drop_table('youtube_videos')
