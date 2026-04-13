"""create_initial_tables_base

Revision ID: 3a83dd84ed15
Revises: 
Create Date: 2025-09-27 01:05:52.655716

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '3a83dd84ed15'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables without voice_id column."""
    # Create pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create personas table (without voice_id - that's added in next migration)
    op.create_table('personas',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=255), nullable=True),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )

    # Create content_chunks table
    op.create_table('content_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create patterns table
    op.create_table('patterns',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('pattern_type', sa.String(length=100), nullable=False),
        sa.Column('pattern_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create conversations table (without conversation_type - that's added in migration 15fa73ba2dc4)
    op.create_table('conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('user_email', sa.String(length=255), nullable=True),
        sa.Column('messages', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('conversation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create external_data_sources table
    op.create_table('external_data_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('data_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create data_llamaindex_embeddings table (base structure that LlamaIndex creates)
    # Note: The migration b2c3d4e5f6a7 works on data_data_llamaindex_embeddings which is a different table
    op.create_table('data_llamaindex_embeddings',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('node_id', sa.String(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('metadata_', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create data_data_llamaindex_embeddings table (what the migration b2c3d4e5f6a7 expects)
    op.create_table('data_data_llamaindex_embeddings',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('node_id', sa.String(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('metadata_', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create api_keys table for API key authentication
    # Create the enum type if it doesn't exist
    apikeyscope = postgresql.ENUM('BACKEND', 'FRONTEND', 'ADMIN', 'READ_ONLY', name='apikeyscope', create_type=False)
    apikeyscope.create(op.get_bind(), checkfirst=True)
    
    op.create_table('api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key_hash', sa.String(length=255), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('scope', postgresql.ENUM('BACKEND', 'FRONTEND', 'ADMIN', 'READ_ONLY', name='apikeyscope', create_type=False), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    
    # Create user_sessions table for session management
    op.create_table('user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('session_token', sa.String(length=500), nullable=False),
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_accessed', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('session_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_token')
    )
    
    # Create indexes for user_sessions
    op.create_index('idx_user_sessions_user_email', 'user_sessions', ['user_email'], unique=False)
    op.create_index('idx_user_sessions_session_token', 'user_sessions', ['session_token'], unique=False)
    op.create_index('idx_user_sessions_persona_id', 'user_sessions', ['persona_id'], unique=False)
    op.create_index('idx_user_sessions_expires_at', 'user_sessions', ['expires_at'], unique=False)
    op.create_index('idx_user_sessions_active', 'user_sessions', ['is_active'], unique=False)


def downgrade() -> None:
    """Drop all initial tables."""
    # Drop indexes first
    op.drop_index('idx_user_sessions_active', table_name='user_sessions')
    op.drop_index('idx_user_sessions_expires_at', table_name='user_sessions')
    op.drop_index('idx_user_sessions_persona_id', table_name='user_sessions')
    op.drop_index('idx_user_sessions_session_token', table_name='user_sessions')
    op.drop_index('idx_user_sessions_user_email', table_name='user_sessions')
    
    # Drop tables
    op.drop_table('user_sessions')
    op.drop_table('api_keys')
    op.drop_table('data_data_llamaindex_embeddings')
    op.drop_table('data_llamaindex_embeddings')
    op.drop_table('external_data_sources')
    op.drop_table('conversations')
    op.drop_table('patterns')
    op.drop_table('content_chunks')
    op.drop_table('personas')
    
    # Drop enum type
    op.execute('DROP TYPE IF EXISTS apikeyscope')
    
    # Drop pgvector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
