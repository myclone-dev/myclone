"""Add content_type and posted_at to content_chunks

Revision ID: 6b36ed7a194f
Revises: f95f7928ac89
Create Date: 2025-09-27T03:29:39.619387

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6b36ed7a194f'
down_revision: Union[str, Sequence[str], None] = ('f95f7928ac89', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add content_type column to differentiate between profile and posts
    op.add_column('content_chunks', sa.Column('content_type', sa.String(length=100), nullable=True))

    # Add posted_at column for posts/tweets temporal information
    op.add_column('content_chunks', sa.Column('posted_at', sa.DateTime(), nullable=True))

    # Update existing rows to set content_type based on source field and metadata
    # Profile content typically has 'linkedin_profile', 'twitter_profile' sources
    # Posts/tweets would have other indicators in metadata
    op.execute("""
        UPDATE content_chunks
        SET content_type = CASE
            -- Check metadata first for explicit content_type
            WHEN metadata->>'content_type' = 'profile' THEN 'profile'
            WHEN metadata->>'content_type' = 'post' THEN 'post'
            WHEN metadata->>'content_type' = 'tweet' THEN 'tweet'
            WHEN metadata->>'content_type' = 'page' THEN 'page'
            -- Infer from source patterns
            WHEN source LIKE '%profile%' THEN 'profile'
            WHEN source = 'linkedin_profile' THEN 'profile'
            WHEN source = 'twitter_profile' THEN 'profile'
            -- Infer from metadata fields
            WHEN source = 'linkedin' AND metadata->>'post_url' IS NOT NULL THEN 'post'
            WHEN source = 'twitter' AND metadata->>'tweet_id' IS NOT NULL THEN 'tweet'
            WHEN source = 'twitter' AND metadata->>'username' IS NOT NULL AND metadata->>'tweet_id' IS NULL THEN 'profile'
            WHEN source = 'linkedin' AND metadata->>'url' IS NOT NULL AND metadata->>'post_url' IS NULL THEN 'profile'
            -- Website pages
            WHEN source = 'website' OR source = 'website_content' THEN 'page'
            -- Default fallback
            ELSE 'unknown'
        END
        WHERE content_type IS NULL OR content_type = 'unknown'
    """)

    # Extract and validate posted_at from metadata if available
    op.execute(r"""
        UPDATE content_chunks
        SET posted_at = CASE
            WHEN metadata->>'posted_at' ~ '^\d{4}-\d{2}-\d{2}'
            THEN (metadata->>'posted_at')::timestamp
            ELSE NULL
        END
        WHERE posted_at IS NULL
        AND metadata->>'posted_at' IS NOT NULL
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the new columns
    op.drop_column('content_chunks', 'posted_at')
    op.drop_column('content_chunks', 'content_type')
