"""create_relationship_tables

Revision ID: ad10d18071d1
Revises: 3675d5d1c636
Create Date: 2025-10-07 19:29:15.123456

This migration creates relationship tables that connect personas to data sources
and provide audit trail for enrichment operations.

Tables created:
1. persona_data_sources - Junction table defining which data sources each persona uses
2. enrichment_audit_log - Audit trail for enrichment operations (replaces external_data_sources)

These tables are the KEY to enabling:
- Multiple personas per user
- Flexible data source selection per persona
- Audit trail for all enrichment operations
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ad10d18071d1'
down_revision: Union[str, Sequence[str], None] = '3675d5d1c636'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create relationship tables."""

    # =========================================================================
    # 1. PERSONA_DATA_SOURCES - Junction table
    # =========================================================================
    op.create_table(
        'persona_data_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_type', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('source_filters', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('enabled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('disabled_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('persona_id', 'source_type', name='uq_persona_data_sources_persona_source'),
        sa.CheckConstraint(
            "source_type IN ('linkedin', 'twitter', 'website', 'pdf', 'github', 'medium', 'youtube', 'document')",
            name='ck_persona_data_sources_valid_source_type'
        ),
        comment='Defines which data sources each persona uses'
    )

    op.create_index('idx_persona_data_sources_persona', 'persona_data_sources', ['persona_id'])
    op.create_index('idx_persona_data_sources_enabled', 'persona_data_sources', ['persona_id', 'enabled'])
    op.create_index('idx_persona_data_sources_source', 'persona_data_sources', ['source_type'])

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_persona_data_sources_updated_at
        BEFORE UPDATE ON persona_data_sources
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
    """)

    # =========================================================================
    # 2. ENRICHMENT_AUDIT_LOG - Audit trail (replaces external_data_sources)
    # =========================================================================
    op.create_table(
        'enrichment_audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_type', sa.Text(), nullable=False),
        sa.Column('enrichment_provider', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), server_default="'completed'", nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Optional references to created data (NULL if enrichment failed)
        sa.Column('linkedin_basic_info_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('scrape_metadata_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('twitter_profile_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Statistics
        sa.Column('records_imported', sa.Integer(), server_default='0', nullable=False),
        sa.Column('posts_imported', sa.Integer(), server_default='0', nullable=False),
        sa.Column('experiences_imported', sa.Integer(), server_default='0', nullable=False),
        sa.Column('pages_imported', sa.Integer(), server_default='0', nullable=False),

        # Timestamps
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),

        # Foreign keys
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['linkedin_basic_info_id'], ['linkedin_basic_info.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['scrape_metadata_id'], ['website_scrape_metadata.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['twitter_profile_id'], ['twitter_profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),

        # Constraints
        sa.CheckConstraint(
            "source_type IN ('linkedin', 'twitter', 'website', 'pdf', 'document')",
            name='ck_enrichment_audit_log_valid_source_type'
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name='ck_enrichment_audit_log_valid_status'
        ),
        comment='Audit trail for enrichments - tracks per user (not persona)'
    )

    op.create_index('idx_enrichment_audit_user_id', 'enrichment_audit_log', ['user_id'])
    op.create_index('idx_enrichment_audit_status', 'enrichment_audit_log', ['user_id', 'status'])
    op.create_index('idx_enrichment_audit_source', 'enrichment_audit_log', ['user_id', 'source_type'])
    op.create_index('idx_enrichment_audit_started', 'enrichment_audit_log', [sa.text('started_at DESC')])


def downgrade() -> None:
    """Drop relationship tables."""

    # Drop tables in reverse order
    op.drop_table('enrichment_audit_log')
    op.drop_table('persona_data_sources')
