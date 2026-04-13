"""create_all_new_data_tables

Revision ID: de2129922b52
Revises: 52fd2e9ac67c
Create Date: 2025-10-07 19:24:56.268463

This migration creates all new tables for the user-centric data model:
- users, auth_details (core user management)
- linkedin_basic_info, linkedin_posts, linkedin_experiences
- twitter_profiles, twitter_posts
- website_scrape_metadata, website_scrape_content
- documents (with generated columns and views)

NO DATA MIGRATION - Schema only. Data migration happens via separate scripts.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'de2129922b52'
down_revision: Union[str, Sequence[str], None] = '52fd2e9ac67c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all new data tables."""

    # =========================================================================
    # 1. USERS TABLE - Core user accounts
    # =========================================================================
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('username', sa.Text(), nullable=False),
        sa.Column('fullname', sa.Text(), nullable=False),
        sa.Column('avatar', sa.Text(), nullable=True),
        sa.Column('linkedin_id', sa.Text(), nullable=True),
        sa.Column('linkedin_url', sa.Text(), nullable=True),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('email_confirmed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('email', name='uq_users_email'),
        sa.UniqueConstraint('username', name='uq_users_username'),
        sa.UniqueConstraint('linkedin_id', name='uq_users_linkedin_id'),
        comment='Core user accounts - owns all enriched data'
    )

    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_linkedin_id', 'users', ['linkedin_id'], postgresql_where=sa.text('linkedin_id IS NOT NULL'))

    # =========================================================================
    # 2. AUTH_DETAILS TABLE - OAuth tokens per platform
    # =========================================================================
    op.create_table(
        'auth_details',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('platform', sa.Text(), nullable=False),
        sa.Column('platform_user_id', sa.Text(), nullable=False),
        sa.Column('platform_username', sa.Text(), nullable=False),
        sa.Column('avatar', sa.Text(), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expiry', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'platform', name='uq_auth_details_user_platform'),
        sa.CheckConstraint(
            "platform IN ('google', 'linkedin', 'github', 'twitter')",
            name='ck_auth_details_valid_platform'
        ),
        comment='OAuth tokens per platform - encrypted at application level'
    )

    op.create_index('idx_auth_details_user_id', 'auth_details', ['user_id'])

    # =========================================================================
    # 3. LINKEDIN TABLES
    # =========================================================================

    # linkedin_basic_info
    op.create_table(
        'linkedin_basic_info',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('headline', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('profile_picture_url', sa.Text(), nullable=True),
        sa.Column('skills', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('industry', sa.Text(), nullable=True),
        sa.Column('connections_count', sa.Integer(), nullable=True),
        sa.Column('followers_count', sa.Integer(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', name='uq_linkedin_basic_info_user_id'),
        comment='LinkedIn profile - one record per user'
    )

    op.create_index('idx_linkedin_basic_info_user_id', 'linkedin_basic_info', ['user_id'])

    # linkedin_posts
    op.create_table(
        'linkedin_posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('linkedin_post_id', sa.Text(), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('post_url', sa.Text(), nullable=True),
        sa.Column('num_likes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('num_comments', sa.Integer(), server_default='0', nullable=False),
        sa.Column('num_reposts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('linkedin_post_id', name='uq_linkedin_posts_linkedin_post_id'),
        comment='LinkedIn posts - raw data only, embeddings stored in content_chunks'
    )

    op.create_index('idx_linkedin_posts_user_id', 'linkedin_posts', ['user_id'])
    op.create_index('idx_linkedin_posts_posted_at', 'linkedin_posts', [sa.text('posted_at DESC')])

    # linkedin_experiences
    op.create_table(
        'linkedin_experiences',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company', sa.Text(), nullable=False),
        sa.Column('company_linkedin_url', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_current', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        comment='Work experience from LinkedIn - raw data only, embeddings stored in content_chunks'
    )

    op.create_index('idx_linkedin_experiences_user_id', 'linkedin_experiences', ['user_id'])
    op.create_index('idx_linkedin_experiences_current', 'linkedin_experiences', ['user_id'], postgresql_where=sa.text('is_current = true'))

    # =========================================================================
    # 4. TWITTER TABLES
    # =========================================================================

    # twitter_profiles
    op.create_table(
        'twitter_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('twitter_id', sa.Text(), nullable=False),
        sa.Column('username', sa.Text(), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('profile_image_url', sa.Text(), nullable=True),
        sa.Column('verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('followers_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('following_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('tweet_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('website_url', sa.Text(), nullable=True),
        sa.Column('joined_date', sa.Date(), nullable=True),
        sa.Column('last_scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('twitter_id', name='uq_twitter_profiles_twitter_id'),
        sa.UniqueConstraint('username', name='uq_twitter_profiles_username'),
        comment='Twitter profile - one per user'
    )

    op.create_index('idx_twitter_profiles_user_id', 'twitter_profiles', ['user_id'])
    op.create_index('idx_twitter_profiles_twitter_id', 'twitter_profiles', ['twitter_id'])

    # twitter_posts
    op.create_table(
        'twitter_posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('twitter_profile_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tweet_id', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tweet_url', sa.Text(), nullable=True),
        sa.Column('reply_to_tweet_id', sa.Text(), nullable=True),
        sa.Column('retweet_of_tweet_id', sa.Text(), nullable=True),
        sa.Column('num_likes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('num_retweets', sa.Integer(), server_default='0', nullable=False),
        sa.Column('num_replies', sa.Integer(), server_default='0', nullable=False),
        sa.Column('num_views', sa.Integer(), server_default='0', nullable=False),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['twitter_profile_id'], ['twitter_profiles.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('tweet_id', name='uq_twitter_posts_tweet_id'),
        comment='Twitter posts - raw data only, embeddings stored in content_chunks'
    )

    op.create_index('idx_twitter_posts_profile_id', 'twitter_posts', ['twitter_profile_id'])
    op.create_index('idx_twitter_posts_posted_at', 'twitter_posts', [sa.text('posted_at DESC')])

    # =========================================================================
    # 5. WEBSITE SCRAPING TABLES
    # =========================================================================

    # website_scrape_metadata
    op.create_table(
        'website_scrape_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('website_url', sa.Text(), nullable=False),
        sa.Column('scraper', sa.Text(), server_default="'firecrawl'", nullable=False),
        sa.Column('scraping_status', sa.Text(), server_default="'completed'", nullable=False),
        sa.Column('max_pages_crawled', sa.Integer(), server_default='1', nullable=False),
        sa.Column('pages_crawled', sa.Integer(), server_default='1', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('language', sa.Text(), nullable=True),
        sa.Column('author', sa.Text(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            "scraping_status IN ('pending', 'in_progress', 'completed', 'failed')",
            name='ck_website_scrape_metadata_valid_status'
        ),
        comment='Website scraping metadata - one record per scrape job'
    )

    op.create_index('idx_website_scrape_metadata_user_id', 'website_scrape_metadata', ['user_id'])
    op.create_index('idx_website_scrape_metadata_status', 'website_scrape_metadata', ['scraping_status'])

    # website_scrape_content
    op.create_table(
        'website_scrape_content',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('scrape_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('page_url', sa.Text(), nullable=False),
        sa.Column('page_title', sa.Text(), nullable=True),
        sa.Column('content_markdown', sa.Text(), nullable=True),
        sa.Column('content_html', sa.Text(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('page_order', sa.Integer(), server_default='1', nullable=False),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['scrape_id'], ['website_scrape_metadata.id'], ondelete='CASCADE'),
        comment='Individual scraped pages - raw data only, embeddings stored in content_chunks'
    )

    op.create_index('idx_website_scrape_content_scrape_id', 'website_scrape_content', ['scrape_id'])
    op.create_index('idx_website_scrape_content_page_order', 'website_scrape_content', ['scrape_id', 'page_order'])

    # =========================================================================
    # 6. DOCUMENTS TABLE (with generated columns)
    # =========================================================================
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', sa.Text(), nullable=False),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            "document_type IN ('pdf', 'xlsx', 'pptx', 'docx', 'csv', 'txt', 'md')",
            name='ck_documents_valid_type'
        ),
        comment='All document types - raw data only, embeddings stored in content_chunks'
    )

    # Add generated columns using raw SQL (SQLAlchemy doesn't support GENERATED ALWAYS AS)
    op.execute("""
        ALTER TABLE documents
        ADD COLUMN page_count INTEGER GENERATED ALWAYS AS (
            CASE WHEN metadata ? 'page_count'
            THEN (metadata->>'page_count')::int
            ELSE NULL END
        ) STORED
    """)

    op.execute("""
        ALTER TABLE documents
        ADD COLUMN sheet_count INTEGER GENERATED ALWAYS AS (
            CASE WHEN metadata ? 'sheet_count'
            THEN (metadata->>'sheet_count')::int
            ELSE NULL END
        ) STORED
    """)

    op.execute("""
        ALTER TABLE documents
        ADD COLUMN slide_count INTEGER GENERATED ALWAYS AS (
            CASE WHEN metadata ? 'slide_count'
            THEN (metadata->>'slide_count')::int
            ELSE NULL END
        ) STORED
    """)

    # Add CHECK constraints on generated columns
    op.create_check_constraint(
        'ck_documents_valid_pdf_metadata',
        'documents',
        "document_type != 'pdf' OR (metadata ? 'page_count' AND page_count > 0)"
    )

    op.create_check_constraint(
        'ck_documents_valid_excel_metadata',
        'documents',
        "document_type != 'xlsx' OR (metadata ? 'sheet_count' AND sheet_count > 0)"
    )

    op.create_check_constraint(
        'ck_documents_valid_pptx_metadata',
        'documents',
        "document_type != 'pptx' OR (metadata ? 'slide_count' AND slide_count > 0)"
    )

    # Create indexes
    op.create_index('idx_documents_user_id', 'documents', ['user_id'])
    op.create_index('idx_documents_type', 'documents', ['document_type'])
    op.create_index('idx_documents_pdf_pages', 'documents', ['page_count'],
                    postgresql_where=sa.text("document_type = 'pdf' AND page_count IS NOT NULL"))
    op.create_index('idx_documents_excel_sheets', 'documents', ['sheet_count'],
                    postgresql_where=sa.text("document_type = 'xlsx' AND sheet_count IS NOT NULL"))
    op.create_index('idx_documents_pptx_slides', 'documents', ['slide_count'],
                    postgresql_where=sa.text("document_type = 'pptx' AND slide_count IS NOT NULL"))

    # Create views for type-safe access
    op.execute("""
        CREATE VIEW pdf_documents AS
        SELECT
            id,
            user_id,
            filename,
            file_size,
            content_text,
            page_count,
            metadata->>'extraction_quality' AS extraction_quality,
            metadata->>'parser' AS parser,
            uploaded_at,
            created_at,
            updated_at
        FROM documents
        WHERE document_type = 'pdf'
    """)

    op.execute("""
        CREATE VIEW excel_documents AS
        SELECT
            id,
            user_id,
            filename,
            file_size,
            content_text,
            sheet_count,
            metadata->'sheet_names' AS sheet_names,
            (metadata->>'total_rows')::int AS total_rows,
            uploaded_at,
            created_at,
            updated_at
        FROM documents
        WHERE document_type = 'xlsx'
    """)

    op.execute("""
        CREATE VIEW powerpoint_documents AS
        SELECT
            id,
            user_id,
            filename,
            file_size,
            content_text,
            slide_count,
            (metadata->>'has_notes')::boolean AS has_notes,
            metadata->>'theme' AS theme,
            uploaded_at,
            created_at,
            updated_at
        FROM documents
        WHERE document_type = 'pptx'
    """)

    # =========================================================================
    # 7. TRIGGERS for updated_at columns
    # =========================================================================

    # Create or replace trigger function (safe if already exists)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    """)

    # Create triggers for all tables with updated_at
    for table_name in ['users', 'auth_details', 'linkedin_basic_info', 'linkedin_posts',
                       'linkedin_experiences', 'twitter_profiles', 'website_scrape_metadata', 'documents']:
        op.execute(f"""
            CREATE TRIGGER update_{table_name}_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
        """)


def downgrade() -> None:
    """Drop all new data tables."""

    # Drop views first
    op.execute('DROP VIEW IF EXISTS powerpoint_documents')
    op.execute('DROP VIEW IF EXISTS excel_documents')
    op.execute('DROP VIEW IF EXISTS pdf_documents')

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('documents')
    op.drop_table('website_scrape_content')
    op.drop_table('website_scrape_metadata')
    op.drop_table('twitter_posts')
    op.drop_table('twitter_profiles')
    op.drop_table('linkedin_experiences')
    op.drop_table('linkedin_posts')
    op.drop_table('linkedin_basic_info')
    op.drop_table('auth_details')
    op.drop_table('users')

    # Note: We don't drop the trigger function as it might be used by other tables
