"""Improve embeddings schema

Revision ID: b2c3d4e5f6a7
Revises: f95f7928ac89
Create Date: 2025-09-17 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'f95f7928ac89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add proper columns and indexes to embeddings table."""

    # Add persona_id column
    op.add_column('data_data_llamaindex_embeddings',
                  sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Add content_chunk_id column
    op.add_column('data_data_llamaindex_embeddings',
                  sa.Column('content_chunk_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Add chunk_index column
    op.add_column('data_data_llamaindex_embeddings',
                  sa.Column('chunk_index', sa.Integer(), nullable=True))

    # Populate persona_id from metadata JSON
    op.execute("""
        UPDATE data_data_llamaindex_embeddings
        SET persona_id = (metadata_->>'persona_id')::uuid
        WHERE persona_id IS NULL
          AND metadata_->>'persona_id' IS NOT NULL
    """)

    # Populate chunk_index from chunk_id in metadata
    op.execute("""
        UPDATE data_data_llamaindex_embeddings
        SET chunk_index = (
            CASE
                WHEN metadata_->>'chunk_id' ~ '_[0-9]+$'
                THEN SPLIT_PART(metadata_->>'chunk_id', '_', -1)::integer
                ELSE 0
            END
        )
        WHERE chunk_index IS NULL
          AND metadata_->>'chunk_id' IS NOT NULL
    """)

    # Populate content_chunk_id by matching with content_chunks table
    op.execute("""
        UPDATE data_data_llamaindex_embeddings e
        SET content_chunk_id = c.id
        FROM content_chunks c
        WHERE e.persona_id = c.persona_id
          AND e.chunk_index = c.chunk_index
          AND e.content_chunk_id IS NULL
    """)

    # Create indexes for better performance
    op.create_index('idx_embeddings_persona_id',
                    'data_data_llamaindex_embeddings',
                    ['persona_id'],
                    unique=False)

    op.create_index('idx_embeddings_chunk_id',
                    'data_data_llamaindex_embeddings',
                    ['content_chunk_id'],
                    unique=False)

    op.create_index('idx_embeddings_persona_chunk',
                    'data_data_llamaindex_embeddings',
                    ['persona_id', 'chunk_index'],
                    unique=False)

    # Create helper view for easier querying
    op.execute("""
        CREATE OR REPLACE VIEW v_persona_embeddings AS
        SELECT
            e.id as embedding_id,
            e.persona_id,
            e.content_chunk_id,
            e.chunk_index,
            e.node_id,
            e.embedding IS NOT NULL as has_vector,
            c.source,
            c.content,
            c.metadata as chunk_metadata,
            p.name as persona_name,
            p.username as persona_username
        FROM data_data_llamaindex_embeddings e
        LEFT JOIN content_chunks c ON e.content_chunk_id = c.id
        LEFT JOIN personas p ON e.persona_id = p.id
    """)


    # Create optimized query function
    op.execute("""
        CREATE OR REPLACE FUNCTION get_persona_embeddings(p_persona_id UUID)
        RETURNS TABLE (
            embedding_id BIGINT,
            chunk_index INTEGER,
            source VARCHAR,
            content TEXT,
            has_vector BOOLEAN
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                e.id,
                e.chunk_index,
                c.source,
                c.content,
                e.embedding IS NOT NULL
            FROM data_data_llamaindex_embeddings e
            LEFT JOIN content_chunks c ON e.content_chunk_id = c.id
            WHERE e.persona_id = p_persona_id
            ORDER BY e.chunk_index;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Note: Function permissions managed by database administrator in production environments

    # Optionally add foreign key constraints (commented out by default)
    # op.create_foreign_key('fk_embeddings_persona',
    #                       'data_data_llamaindex_embeddings',
    #                       'personas',
    #                       ['persona_id'],
    #                       ['id'],
    #                       ondelete='CASCADE')
    #
    # op.create_foreign_key('fk_embeddings_chunk',
    #                       'data_data_llamaindex_embeddings',
    #                       'content_chunks',
    #                       ['content_chunk_id'],
    #                       ['id'],
    #                       ondelete='CASCADE')


def downgrade() -> None:
    """Remove columns and indexes from embeddings table."""

    # Drop the function
    op.execute("DROP FUNCTION IF EXISTS get_persona_embeddings(UUID)")

    # Drop the view
    op.execute("DROP VIEW IF EXISTS v_persona_embeddings")

    # Drop foreign key constraints if they exist
    # op.drop_constraint('fk_embeddings_persona', 'data_data_llamaindex_embeddings', type_='foreignkey')
    # op.drop_constraint('fk_embeddings_chunk', 'data_data_llamaindex_embeddings', type_='foreignkey')

    # Drop indexes
    op.drop_index('idx_embeddings_persona_chunk', table_name='data_data_llamaindex_embeddings')
    op.drop_index('idx_embeddings_chunk_id', table_name='data_data_llamaindex_embeddings')
    op.drop_index('idx_embeddings_persona_id', table_name='data_data_llamaindex_embeddings')

    # Drop columns
    op.drop_column('data_data_llamaindex_embeddings', 'chunk_index')
    op.drop_column('data_data_llamaindex_embeddings', 'content_chunk_id')
    op.drop_column('data_data_llamaindex_embeddings', 'persona_id')