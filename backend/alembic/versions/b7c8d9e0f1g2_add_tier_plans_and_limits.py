"""add_tier_plans_and_limits

Revision ID: b7c8d9e0f1g2
Revises: 22883c686f45
Create Date: 2025-10-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1g2'
down_revision: Union[str, Sequence[str], None] = '22883c686f45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add tier-based subscription and usage tracking system.

    Architecture:
    1. tier_plans - Define available subscription tiers
    2. user_subscriptions - Track user subscription history and status
    3. user_usage_cache - Cache usage metrics to avoid expensive aggregations

    Tier system controls:
    1. Raw text files (txt, md) - separate storage limits
    2. Document files (pdf, docx, xlsx, pptx) - parsing required, separate limits
    3. Multimedia (audio, video) - separate limits with duration tracking (6 hours hard limit)
    4. YouTube - duration limits only (2 hours max per video, 1000 videos hard limit)
    """

    # Check if tables already exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # ========== 1. CREATE TIER_PLANS TABLE ==========
    if 'tier_plans' not in tables:
        op.create_table(
            'tier_plans',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tier_name', sa.String(50), nullable=False),

            # Raw text file limits (txt, md)
            sa.Column('max_raw_text_storage_mb', sa.Integer(), nullable=False,
                      comment='Max storage for raw text files (txt, md)'),
            sa.Column('max_raw_text_files', sa.Integer(), nullable=False,
                      comment='Max number of raw text files'),

            # Document file limits (pdf, docx, xlsx, pptx, etc)
            sa.Column('max_document_file_size_mb', sa.Integer(), nullable=False,
                      comment='Max single document file size'),
            sa.Column('max_document_storage_mb', sa.Integer(), nullable=False,
                      comment='Total storage for document files'),
            sa.Column('max_document_files', sa.Integer(), nullable=False,
                      comment='Max number of document files'),

            # Multimedia file limits (audio, video) - 6 hours hard duration limit
            sa.Column('max_multimedia_file_size_mb', sa.Integer(), nullable=False,
                      comment='Max single multimedia file size'),
            sa.Column('max_multimedia_storage_mb', sa.Integer(), nullable=False,
                      comment='Total storage for multimedia files'),
            sa.Column('max_multimedia_files', sa.Integer(), nullable=False,
                      comment='Max number of multimedia files'),
            sa.Column('max_multimedia_duration_hours', sa.Integer(), nullable=False,
                      comment='Total duration limit (hard limit: 6 hours)'),

            # YouTube ingestion limits - duration-based only
            sa.Column('max_youtube_videos', sa.Integer(), nullable=False,
                      comment='Max YouTube videos (hard limit: 1000)'),
            sa.Column('max_youtube_video_duration_minutes', sa.Integer(), nullable=False,
                      comment='Max single video duration (hard limit: 120 min)'),
            sa.Column('max_youtube_total_duration_hours', sa.Integer(), nullable=False,
                      comment='Total YouTube duration across all videos'),

            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),

            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('tier_name', name='uq_tier_plans_tier_name')
        )

        # Insert tier plan data with explicit IDs
        # ID 0 = free, 1 = pro, 2 = business, 3 = enterprise
        # -1 means unlimited for enterprise tier
        op.execute("""
            INSERT INTO tier_plans (
                id, tier_name,
                max_raw_text_storage_mb, max_raw_text_files,
                max_document_file_size_mb, max_document_storage_mb, max_document_files,
                max_multimedia_file_size_mb, max_multimedia_storage_mb, max_multimedia_files, max_multimedia_duration_hours,
                max_youtube_videos, max_youtube_video_duration_minutes, max_youtube_total_duration_hours
            ) VALUES
            -- FREE TIER (ID = 0): Very limited access
            (
                0, 'free',
                10, 5,              -- Raw text: 10MB total, 5 files
                10, 50, 3,          -- Documents: 10MB per file, 50MB total, 3 files
                50, 100, 2, 1,      -- Multimedia: 50MB per file, 100MB total, 2 files, 1 hour total
                5, 30, 2            -- YouTube: 5 videos, 30 min per video, 2 hours total
            ),
            -- PRO TIER (ID = 1): Individual creators
            (
                1, 'pro',
                100, 50,            -- Raw text: 100MB total, 50 files
                50, 1000, 30,       -- Documents: 50MB per file, 1GB total, 30 files
                200, 2000, 20, 6,   -- Multimedia: 200MB per file, 2GB total, 20 files, 6 hours total (hard limit)
                100, 120, 20        -- YouTube: 100 videos, 120 min per video (hard limit), 20 hours total
            ),
            -- BUSINESS TIER (ID = 2): Small teams
            (
                2, 'business',
                500, 200,           -- Raw text: 500MB total, 200 files
                200, 10000, 200,    -- Documents: 200MB per file, 10GB total, 200 files
                500, 20000, 100, 6, -- Multimedia: 500MB per file, 20GB total, 100 files, 6 hours total (hard limit)
                500, 120, 100       -- YouTube: 500 videos, 120 min per video (hard limit), 100 hours total
            ),
            -- ENTERPRISE TIER (ID = 3): Unlimited (within hard limits)
            (
                3, 'enterprise',
                -1, -1,             -- Raw text: unlimited
                -1, -1, -1,         -- Documents: unlimited
                -1, -1, -1, 6,      -- Multimedia: unlimited storage/files, but 6 hours duration (hard limit)
                1000, 120, -1       -- YouTube: 1000 videos (hard limit), 120 min per video (hard limit), unlimited total duration
            );
        """)

        # Set sequence to start after explicit IDs
        op.execute("SELECT setval('tier_plans_id_seq', 4, false);")

    # ========== 2. CREATE USER_SUBSCRIPTIONS TABLE ==========
    if 'user_subscriptions' not in tables:
        op.create_table(
            'user_subscriptions',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('tier_id', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('subscription_start_date', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('subscription_end_date', sa.DateTime(timezone=True), nullable=True,
                      comment='NULL means lifetime/no expiry'),
            sa.Column('status', sa.Enum('active', 'expired', 'cancelled', 'pending',
                      name='subscription_status_enum'), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),

            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['tier_id'], ['tier_plans.id'])
        )

        # Create unique partial index to ensure only one active subscription per user
        op.execute("""
            CREATE UNIQUE INDEX idx_user_subscriptions_user_active 
            ON user_subscriptions (user_id) 
            WHERE status = 'active'
        """)

        # Create other indexes
        op.create_index('idx_user_subscriptions_user_end_date', 'user_subscriptions',
                       ['user_id', 'subscription_end_date'])
        op.create_index('idx_user_subscriptions_status_end_date', 'user_subscriptions',
                       ['status', 'subscription_end_date'])

        # Migrate existing users to free tier with active subscriptions
        op.execute("""
            INSERT INTO user_subscriptions (user_id, tier_id, subscription_start_date, subscription_end_date, status)
            SELECT 
                id as user_id,
                0 as tier_id,
                '2025-10-28 00:00:00+00'::timestamptz as subscription_start_date,
                '2026-10-28 00:00:00+00'::timestamptz as subscription_end_date,
                'active' as status
            FROM users
        """)

    # ========== 3. CREATE USER_USAGE_CACHE TABLE ==========
    if 'user_usage_cache' not in tables:
        op.create_table(
            'user_usage_cache',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),

            # Raw Text Tracking
            sa.Column('raw_text_storage_bytes', sa.BigInteger(), nullable=False, server_default='0',
                      comment='Total storage used by raw text files'),
            sa.Column('raw_text_file_count', sa.Integer(), nullable=False, server_default='0',
                      comment='Number of raw text files'),

            # Document Tracking
            sa.Column('document_storage_bytes', sa.BigInteger(), nullable=False, server_default='0',
                      comment='Total storage used by document files'),
            sa.Column('document_file_count', sa.Integer(), nullable=False, server_default='0',
                      comment='Number of document files'),

            # Multimedia Tracking
            sa.Column('multimedia_storage_bytes', sa.BigInteger(), nullable=False, server_default='0',
                      comment='Total storage used by multimedia files'),
            sa.Column('multimedia_file_count', sa.Integer(), nullable=False, server_default='0',
                      comment='Number of multimedia files'),
            sa.Column('multimedia_total_duration_seconds', sa.BigInteger(), nullable=False, server_default='0',
                      comment='Total duration of multimedia files in seconds'),

            # YouTube Tracking
            sa.Column('youtube_video_count', sa.Integer(), nullable=False, server_default='0',
                      comment='Number of YouTube videos ingested'),
            sa.Column('youtube_total_duration_seconds', sa.BigInteger(), nullable=False, server_default='0',
                      comment='Total duration of YouTube videos in seconds'),

            sa.Column('last_updated_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),

            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('user_id', name='uq_user_usage_cache_user_id')
        )

        # Create index on user_id for fast lookups
        op.create_index('idx_user_usage_cache_user_id', 'user_usage_cache', ['user_id'])

        # Initialize usage cache for all existing users
        op.execute("""
            INSERT INTO user_usage_cache (user_id)
            SELECT id FROM users
        """)


def downgrade() -> None:
    """Remove tier plans, subscriptions, and usage tracking tables"""

    # Check if objects exist before dropping
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # Drop user_usage_cache table
    if 'user_usage_cache' in tables:
        op.drop_index('idx_user_usage_cache_user_id', table_name='user_usage_cache')
        op.drop_table('user_usage_cache')

    # Drop user_subscriptions table
    if 'user_subscriptions' in tables:
        op.drop_index('idx_user_subscriptions_status_end_date', table_name='user_subscriptions')
        op.drop_index('idx_user_subscriptions_user_end_date', table_name='user_subscriptions')
        op.execute("DROP INDEX IF EXISTS idx_user_subscriptions_user_active")
        op.drop_table('user_subscriptions')

    # Drop subscription_status_enum type
    op.execute("DROP TYPE IF EXISTS subscription_status_enum")

    # Drop tier_plans table
    if 'tier_plans' in tables:
        op.drop_table('tier_plans')

