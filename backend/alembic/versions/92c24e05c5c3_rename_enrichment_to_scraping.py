"""rename_enrichment_to_scraping

Revision ID: 92c24e05c5c3
Revises: c9d793229de0
Create Date: 2025-10-10

Renames enrichment_audit_log table to scraping_jobs to align terminology
with actual functionality (job status tracking, not audit logging).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92c24e05c5c3'
down_revision: Union[str, None] = 'c9d793229de0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename enrichment_audit_log to scraping_jobs"""

    # Rename the table
    op.rename_table('enrichment_audit_log', 'scraping_jobs')

    # Rename the column
    op.alter_column('scraping_jobs', 'enrichment_provider', new_column_name='scraping_provider')

    # Rename indexes
    op.drop_index('idx_enrichment_audit_user_id', table_name='scraping_jobs')
    op.create_index('idx_scraping_jobs_user_id', 'scraping_jobs', ['user_id'])

    op.drop_index('idx_enrichment_audit_status', table_name='scraping_jobs')
    op.create_index('idx_scraping_jobs_status', 'scraping_jobs', ['user_id', 'status'])

    op.drop_index('idx_enrichment_audit_source', table_name='scraping_jobs')
    op.create_index('idx_scraping_jobs_source', 'scraping_jobs', ['user_id', 'source_type'])

    op.drop_index('idx_enrichment_audit_started', table_name='scraping_jobs')
    op.execute('CREATE INDEX idx_scraping_jobs_started ON scraping_jobs (started_at DESC)')

    # Rename check constraints
    op.drop_constraint('ck_enrichment_audit_log_valid_source_type', 'scraping_jobs', type_='check')
    op.create_check_constraint(
        'ck_scraping_jobs_valid_source_type',
        'scraping_jobs',
        "source_type IN ('linkedin', 'twitter', 'website', 'pdf', 'document')"
    )

    op.drop_constraint('ck_enrichment_audit_log_valid_status', 'scraping_jobs', type_='check')
    op.create_check_constraint(
        'ck_scraping_jobs_valid_status',
        'scraping_jobs',
        "status IN ('pending', 'processing', 'completed', 'failed', 'queued')"
    )


def downgrade() -> None:
    """Revert scraping_jobs back to enrichment_audit_log"""

    # Rename check constraints back
    op.drop_constraint('ck_scraping_jobs_valid_status', 'scraping_jobs', type_='check')
    op.create_check_constraint(
        'ck_enrichment_audit_log_valid_status',
        'scraping_jobs',
        "status IN ('pending', 'processing', 'completed', 'failed', 'queued')"
    )

    op.drop_constraint('ck_scraping_jobs_valid_source_type', 'scraping_jobs', type_='check')
    op.create_check_constraint(
        'ck_enrichment_audit_log_valid_source_type',
        'scraping_jobs',
        "source_type IN ('linkedin', 'twitter', 'website', 'pdf', 'document')"
    )

    # Rename indexes back
    op.drop_index('idx_scraping_jobs_started', table_name='scraping_jobs')
    op.execute('CREATE INDEX idx_enrichment_audit_started ON scraping_jobs (started_at DESC)')

    op.drop_index('idx_scraping_jobs_source', table_name='scraping_jobs')
    op.create_index('idx_enrichment_audit_source', 'scraping_jobs', ['user_id', 'source_type'])

    op.drop_index('idx_scraping_jobs_status', table_name='scraping_jobs')
    op.create_index('idx_enrichment_audit_status', 'scraping_jobs', ['user_id', 'status'])

    op.drop_index('idx_scraping_jobs_user_id', table_name='scraping_jobs')
    op.create_index('idx_enrichment_audit_user_id', 'scraping_jobs', ['user_id'])

    # Rename the column back
    op.alter_column('scraping_jobs', 'scraping_provider', new_column_name='enrichment_provider')

    # Rename the table back
    op.rename_table('scraping_jobs', 'enrichment_audit_log')
