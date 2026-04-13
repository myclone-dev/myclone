"""add archived status to scraping jobs

Revision ID: 22883c686f45
Revises: a1f2b3c4d5e6
Create Date: 2025-10-28 22:29:17.323415

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22883c686f45'
down_revision: Union[str, Sequence[str], None] = 'a1f2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the old constraint
    op.drop_constraint('ck_scraping_jobs_valid_status', 'scraping_jobs', type_='check')

    # Create new constraint with 'archived' status
    op.create_check_constraint(
        'ck_scraping_jobs_valid_status',
        'scraping_jobs',
        "status IN ('pending', 'processing', 'completed', 'failed', 'queued', 'archived')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the new constraint
    op.drop_constraint('ck_scraping_jobs_valid_status', 'scraping_jobs', type_='check')

    # Data migration: Convert archived jobs back to failed (since archived only applies to failed jobs)
    op.execute("UPDATE scraping_jobs SET status = 'failed' WHERE status = 'archived'")

    # Restore old constraint without 'archived' status
    op.create_check_constraint(
        'ck_scraping_jobs_valid_status',
        'scraping_jobs',
        "status IN ('pending', 'processing', 'completed', 'failed', 'queued')"
    )
