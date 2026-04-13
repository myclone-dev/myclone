"""add_hnsw_index_to_data_data_llamaindex_embeddings

Revision ID: c7365969ce1a
Revises: 8f5868f915c7
Create Date: 2025-09-30 20:29:07.133040

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7365969ce1a'
down_revision: Union[str, Sequence[str], None] = '8f5868f915c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add HNSW index to data_data_llamaindex_embeddings.embedding for faster vector similarity search."""
    op.execute("""
        CREATE INDEX IF NOT EXISTS data_data_llamaindex_embeddings_embedding_idx
        ON data_data_llamaindex_embeddings
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    """Remove HNSW index from data_data_llamaindex_embeddings.embedding."""
    op.execute("DROP INDEX IF EXISTS data_data_llamaindex_embeddings_embedding_idx")
