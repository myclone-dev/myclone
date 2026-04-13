"""cleanup_rename_llamaindex_embeddings_table

Revision ID: ec9c6a8edf0b
Revises: c4054f839ff4
Create Date: 2025-10-11 17:29:29.456497

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec9c6a8edf0b'
down_revision: Union[str, Sequence[str], None] = 'c4054f839ff4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Clean up duplicate LlamaIndex embeddings tables:
    1. Drop unused data_llamaindex_embeddings table
    2. Rename data_data_llamaindex_embeddings to data_llamaindex_embeddings
    3. Update all related indexes and sequences

    After this migration, the code will use table_name="llamaindex_embeddings"
    which LlamaIndex will prepend with "data_" to get "data_llamaindex_embeddings"
    """

    # Step 1: Drop the unused table created by Alembic
    op.execute("DROP TABLE IF EXISTS data_llamaindex_embeddings CASCADE")

    # Step 2: Rename the actual table (the one with enhancements)
    op.execute("ALTER TABLE data_data_llamaindex_embeddings RENAME TO data_llamaindex_embeddings")

    # Step 3: Rename the sequence
    op.execute("""
        ALTER SEQUENCE data_data_llamaindex_embeddings_id_seq
        RENAME TO data_llamaindex_embeddings_id_seq
    """)

    # Step 4: Rename the primary key constraint
    op.execute("""
        ALTER INDEX data_data_llamaindex_embeddings_pkey
        RENAME TO data_llamaindex_embeddings_pkey
    """)

    # Step 5: Rename the HNSW vector index
    op.execute("""
        ALTER INDEX data_data_llamaindex_embeddings_embedding_idx
        RENAME TO data_llamaindex_embeddings_embedding_idx
    """)

    # Note: Other indexes (idx_embeddings_*) don't need renaming as they don't
    # reference the table name directly


def downgrade() -> None:
    """
    Reverse the cleanup (restore duplicate tables).
    This is mainly for rollback purposes - not recommended in production.
    """

    # Rename back to data_data_llamaindex_embeddings
    op.execute("ALTER TABLE data_llamaindex_embeddings RENAME TO data_data_llamaindex_embeddings")

    # Rename sequence back
    op.execute("""
        ALTER SEQUENCE data_llamaindex_embeddings_id_seq
        RENAME TO data_data_llamaindex_embeddings_id_seq
    """)

    # Rename indexes back
    op.execute("""
        ALTER INDEX data_llamaindex_embeddings_pkey
        RENAME TO data_data_llamaindex_embeddings_pkey
    """)

    op.execute("""
        ALTER INDEX data_llamaindex_embeddings_embedding_idx
        RENAME TO data_data_llamaindex_embeddings_embedding_idx
    """)

    # Recreate the unused table (for consistency)
    from pgvector.sqlalchemy import Vector
    from sqlalchemy.dialects import postgresql

    op.create_table('data_llamaindex_embeddings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('node_id', sa.String(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('metadata_', postgresql.JSONB(), nullable=True),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
