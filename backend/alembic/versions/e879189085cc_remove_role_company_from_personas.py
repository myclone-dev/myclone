"""remove_role_company_from_personas

Revision ID: e879189085cc
Revises: 6zze0hn3mbdo
Create Date: 2025-10-22 04:45:25.338808

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e879189085cc'
down_revision: Union[str, Sequence[str], None] = '6zze0hn3mbdo'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove role and company columns from personas table.

    These fields are now queried dynamically from linkedin_experiences
    where is_current = true, providing a single source of truth.
    """
    # Drop role and company columns from personas table
    op.drop_column('personas', 'role')
    op.drop_column('personas', 'company')


def downgrade() -> None:
    """
    Restore role and company columns to personas table.

    Note: Data will not be restored automatically.
    """
    # Re-add role and company columns
    op.add_column('personas', sa.Column('role', sa.String(length=255), nullable=True))
    op.add_column('personas', sa.Column('company', sa.String(length=255), nullable=True))
