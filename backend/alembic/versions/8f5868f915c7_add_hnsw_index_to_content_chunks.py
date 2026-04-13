"""add_hnsw_index_to_content_chunks

Revision ID: 8f5868f915c7
Revises: a1b2c3d4e5f6
Create Date: 2025-09-30 20:21:05.342490

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f5868f915c7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add HNSW index to content_chunks.embedding for faster vector similarity search."""
    op.execute("""
        CREATE INDEX IF NOT EXISTS content_chunks_embedding_idx
        ON content_chunks
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    """Remove HNSW index from content_chunks.embedding."""
    op.execute("DROP INDEX IF EXISTS content_chunks_embedding_idx")
