"""add_voyage_lite_embeddings_table

Revision ID: abc123def456
Revises: 3d48659cd397
Create Date: 2025-11-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID


# revision identifiers, used by Alembic.
revision: str = "abc123def456"
down_revision: Union[str, Sequence[str], None] = "3d48659cd397"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create data_llamalite_embeddings table for Voyage AI voyage-3.5-lite embeddings (512 dimensions).

    This table has the same structure as data_llamaindex_embeddings but uses 512-dimensional
    vectors instead of 1536. This allows supporting both OpenAI and Voyage AI embeddings
    simultaneously without data loss.
    """
    # Create the new table for Voyage AI embeddings
    op.create_table(
        'data_llamalite_embeddings',
        # LlamaIndex core columns
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('metadata_', JSONB, nullable=True),
        sa.Column('node_id', sa.String(), nullable=True),
        sa.Column('embedding', Vector(512), nullable=True),  # Voyage voyage-3.5-lite 512 dimensions

        # Custom columns for filtering and analytics
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('source_record_id', UUID(as_uuid=True), nullable=True),
        sa.Column('source', sa.Text(), nullable=True),
        sa.Column('source_type', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('text_search_tsv', TSVECTOR, nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
    )
    
    # Create indexes for the new table
    op.create_index('ix_llamalite_user_id', 'data_llamalite_embeddings', ['user_id'])
    op.create_index('ix_llamalite_source_record_id', 'data_llamalite_embeddings', ['source_record_id'])
    op.create_index('ix_llamalite_node_id', 'data_llamalite_embeddings', ['node_id'])
    
    # Create GiST index for text search
    op.execute(
        "CREATE INDEX ix_llamalite_text_search ON data_llamalite_embeddings USING GiST (text_search_tsv)"
    )
    
    # Create trigger to auto-populate text_search_tsv column
    op.execute("""
        CREATE TRIGGER llamalite_text_search_update
        BEFORE INSERT OR UPDATE ON data_llamalite_embeddings
        FOR EACH ROW
        EXECUTE FUNCTION tsvector_update_trigger(text_search_tsv, 'pg_catalog.english', text);
    """)
    
    # Create HNSW index for vector similarity search (same as original table)
    op.execute(
        "CREATE INDEX ix_llamalite_embedding_hnsw ON data_llamalite_embeddings "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    """
    Drop the Voyage AI embeddings table.
    
    WARNING: This will delete all Voyage AI embeddings!
    """
    # Drop indexes first
    op.drop_index('ix_llamalite_embedding_hnsw', table_name='data_llamalite_embeddings')
    op.execute("DROP TRIGGER IF EXISTS llamalite_text_search_update ON data_llamalite_embeddings")
    op.drop_index('ix_llamalite_text_search', table_name='data_llamalite_embeddings')
    op.drop_index('ix_llamalite_node_id', table_name='data_llamalite_embeddings')
    op.drop_index('ix_llamalite_source_record_id', table_name='data_llamalite_embeddings')
    op.drop_index('ix_llamalite_user_id', table_name='data_llamalite_embeddings')
    
    # Drop the table
    op.drop_table('data_llamalite_embeddings')
