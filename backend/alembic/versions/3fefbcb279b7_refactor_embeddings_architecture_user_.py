"""refactor_embeddings_architecture_user_owned

Revision ID: 3fefbcb279b7
Revises: ec9c6a8edf0b
Create Date: 2025-10-11 18:10:10.333726

MAJOR REFACTOR: Move embeddings from persona-owned to user-owned architecture
- Embeddings now belong to users and are shared across personas
- Personas reference which sources to use via persona_data_sources
- Eliminates duplication when multiple personas use the same sources
- Drops content_chunks table (redundant with embeddings)

Changes:
1. data_llamaindex_embeddings: Add user_id, source, source_type, source_record_id
2. data_llamaindex_embeddings: Remove persona_id, content_chunk_id
3. persona_data_sources: Add source_record_id column
4. Drop content_chunks table and related views/functions
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3fefbcb279b7'
down_revision: Union[str, Sequence[str], None] = 'ec9c6a8edf0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Refactor embeddings to user-owned architecture.
    """

    # ====================================================================
    # PART 1: Drop dependent objects that reference content_chunks
    # ====================================================================

    print("Dropping view and function that reference content_chunks...")
    op.execute("DROP VIEW IF EXISTS v_persona_embeddings CASCADE")
    op.execute("DROP FUNCTION IF EXISTS get_persona_embeddings(UUID)")

    # ====================================================================
    # PART 2: Update data_llamaindex_embeddings table
    # ====================================================================

    print("Adding new columns to data_llamaindex_embeddings...")

    # Add new columns (nullable first for safe migration)
    op.add_column('data_llamaindex_embeddings',
                  sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('data_llamaindex_embeddings',
                  sa.Column('source', sa.Text(), nullable=True))
    op.add_column('data_llamaindex_embeddings',
                  sa.Column('source_type', sa.Text(), nullable=True))
    op.add_column('data_llamaindex_embeddings',
                  sa.Column('source_record_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('data_llamaindex_embeddings',
                  sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('data_llamaindex_embeddings',
                  sa.Column('created_at', sa.DateTime(timezone=True),
                           server_default=sa.text('NOW()'), nullable=True))

    # Backfill user_id from persona_id (if data exists)
    print("Backfilling user_id from personas...")
    op.execute("""
        UPDATE data_llamaindex_embeddings e
        SET user_id = p.user_id
        FROM personas p
        WHERE e.persona_id = p.id
          AND e.user_id IS NULL
    """)

    # Make all required fields NOT NULL
    # These fields are required for all embeddings going forward
    op.alter_column('data_llamaindex_embeddings', 'user_id', nullable=False)
    op.alter_column('data_llamaindex_embeddings', 'source', nullable=False)
    op.alter_column('data_llamaindex_embeddings', 'source_record_id', nullable=False)
    op.alter_column('data_llamaindex_embeddings', 'source_type', nullable=False)

    # Create foreign key for user_id
    op.create_foreign_key('fk_embeddings_user',
                         'data_llamaindex_embeddings',
                         'users',
                         ['user_id'],
                         ['id'],
                         ondelete='RESTRICT')

    print("Dropping old columns from data_llamaindex_embeddings...")

    # Drop old indexes first
    op.drop_index('idx_embeddings_persona_id', table_name='data_llamaindex_embeddings')
    op.drop_index('idx_embeddings_chunk_id', table_name='data_llamaindex_embeddings')
    op.drop_index('idx_embeddings_persona_chunk', table_name='data_llamaindex_embeddings')

    # Drop old columns
    op.drop_column('data_llamaindex_embeddings', 'persona_id')
    op.drop_column('data_llamaindex_embeddings', 'content_chunk_id')

    print("Creating new indexes on data_llamaindex_embeddings...")

    # Add new indexes
    op.create_index('idx_embeddings_user_id',
                    'data_llamaindex_embeddings',
                    ['user_id'],
                    unique=False)
    op.create_index('idx_embeddings_source_record',
                    'data_llamaindex_embeddings',
                    ['source_record_id'],
                    unique=False)
    op.create_index('idx_embeddings_source',
                    'data_llamaindex_embeddings',
                    ['source'],
                    unique=False)
    op.create_index('idx_embeddings_user_source',
                    'data_llamaindex_embeddings',
                    ['user_id', 'source'],
                    unique=False)
    op.create_index('idx_embeddings_posted_at',
                    'data_llamaindex_embeddings',
                    [sa.text('posted_at DESC')],
                    unique=False)
    op.create_index('idx_embeddings_source_chunk',
                    'data_llamaindex_embeddings',
                    ['source_record_id', 'chunk_index'],
                    unique=True)

    # ====================================================================
    # PART 3: Update persona_data_sources table
    # ====================================================================

    print("Updating persona_data_sources table...")

    # Add source_record_id column
    op.add_column('persona_data_sources',
                  sa.Column('source_record_id', postgresql.UUID(as_uuid=True), nullable=True,
                           comment='Generic FK to source record (linkedin_basic_info.id, twitter_profiles.id, etc.)'))

    # Drop old unique constraint
    op.drop_constraint('uq_persona_data_sources_persona_source',
                       'persona_data_sources',
                       type_='unique')

    # Add new unique constraint (includes source_record_id)
    op.create_unique_constraint('uq_persona_data_sources_persona_source',
                                'persona_data_sources',
                                ['persona_id', 'source_type', 'source_record_id'])

    # Add index on source_record_id
    op.create_index('idx_persona_data_sources_source_record',
                    'persona_data_sources',
                    ['source_record_id'],
                    unique=False)

    # ====================================================================
    # PART 4: Drop content_chunks table
    # ====================================================================

    print("Dropping content_chunks table...")
    op.drop_table('content_chunks')

    print("Migration complete! Embeddings are now user-owned.")


def downgrade() -> None:
    """
    Rollback to persona-owned embeddings architecture.
    WARNING: This will lose data if embeddings exist without persona mapping.
    """

    # ====================================================================
    # PART 1: Recreate content_chunks table
    # ====================================================================

    print("Recreating content_chunks table...")
    from pgvector.sqlalchemy import Vector

    op.create_table('content_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('source', sa.String(255), nullable=True),
        sa.Column('content_type', sa.String(100), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'])
    )

    # Recreate HNSW index
    op.execute("""
        CREATE INDEX content_chunks_embedding_idx
        ON content_chunks
        USING hnsw (embedding vector_cosine_ops)
    """)

    # ====================================================================
    # PART 2: Revert persona_data_sources
    # ====================================================================

    print("Reverting persona_data_sources...")

    # Drop new index
    op.drop_index('idx_persona_data_sources_source_record',
                  table_name='persona_data_sources')

    # Drop new unique constraint
    op.drop_constraint('uq_persona_data_sources_persona_source',
                       'persona_data_sources',
                       type_='unique')

    # Add old unique constraint
    op.create_unique_constraint('uq_persona_data_sources_persona_source',
                                'persona_data_sources',
                                ['persona_id', 'source_type'])

    # Drop source_record_id column
    op.drop_column('persona_data_sources', 'source_record_id')

    # ====================================================================
    # PART 3: Revert data_llamaindex_embeddings
    # ====================================================================

    print("Reverting data_llamaindex_embeddings...")

    # Drop new indexes
    op.drop_index('idx_embeddings_source_chunk', table_name='data_llamaindex_embeddings')
    op.drop_index('idx_embeddings_posted_at', table_name='data_llamaindex_embeddings')
    op.drop_index('idx_embeddings_user_source', table_name='data_llamaindex_embeddings')
    op.drop_index('idx_embeddings_source', table_name='data_llamaindex_embeddings')
    op.drop_index('idx_embeddings_source_record', table_name='data_llamaindex_embeddings')
    op.drop_index('idx_embeddings_user_id', table_name='data_llamaindex_embeddings')

    # Add back old columns
    op.add_column('data_llamaindex_embeddings',
                  sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('data_llamaindex_embeddings',
                  sa.Column('content_chunk_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Recreate old indexes
    op.create_index('idx_embeddings_persona_chunk',
                    'data_llamaindex_embeddings',
                    ['persona_id', 'chunk_index'],
                    unique=False)
    op.create_index('idx_embeddings_chunk_id',
                    'data_llamaindex_embeddings',
                    ['content_chunk_id'],
                    unique=False)
    op.create_index('idx_embeddings_persona_id',
                    'data_llamaindex_embeddings',
                    ['persona_id'],
                    unique=False)

    # Drop foreign key
    op.drop_constraint('fk_embeddings_user',
                       'data_llamaindex_embeddings',
                       type_='foreignkey')

    # Drop new columns
    op.drop_column('data_llamaindex_embeddings', 'created_at')
    op.drop_column('data_llamaindex_embeddings', 'posted_at')
    op.drop_column('data_llamaindex_embeddings', 'source_record_id')
    op.drop_column('data_llamaindex_embeddings', 'source_type')
    op.drop_column('data_llamaindex_embeddings', 'source')
    op.drop_column('data_llamaindex_embeddings', 'user_id')

    # ====================================================================
    # PART 4: Recreate views and functions
    # ====================================================================

    print("Recreating view and function...")

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
            p.persona_name as persona_username
        FROM data_llamaindex_embeddings e
        LEFT JOIN content_chunks c ON e.content_chunk_id = c.id
        LEFT JOIN personas p ON e.persona_id = p.id
    """)

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
            FROM data_llamaindex_embeddings e
            LEFT JOIN content_chunks c ON e.content_chunk_id = c.id
            WHERE e.persona_id = p_persona_id
            ORDER BY e.chunk_index;
        END;
        $$ LANGUAGE plpgsql;
    """)

    print("Downgrade complete. Reverted to persona-owned architecture.")
