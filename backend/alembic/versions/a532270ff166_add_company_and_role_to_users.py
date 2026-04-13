"""add company and role to users

Revision ID: a532270ff166
Revises: 174efc03f2f3
Create Date: 2025-11-05 10:56:04.323297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a532270ff166'
down_revision: Union[str, Sequence[str], None] = '174efc03f2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add company and role columns to users table."""
    op.add_column('users', sa.Column('company', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('role', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove company and role columns from users table."""
    op.drop_column('users', 'role')
    op.drop_column('users', 'company')
