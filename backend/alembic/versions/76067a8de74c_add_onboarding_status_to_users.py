"""add_onboarding_status_to_users

Revision ID: 76067a8de74c
Revises: f7e91c586b21
Create Date: 2025-10-08 20:47:09.949618

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76067a8de74c'
down_revision: Union[str, Sequence[str], None] = 'f7e91c586b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum type
    onboarding_status_enum = sa.Enum('NOT_STARTED', 'PARTIAL', 'FULLY_ONBOARDED', name='onboarding_status_enum')
    onboarding_status_enum.create(op.get_bind(), checkfirst=True)

    # Add onboarding_status column to users table
    op.add_column('users', sa.Column('onboarding_status', onboarding_status_enum, server_default='NOT_STARTED', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    # Drop onboarding_status column
    op.drop_column('users', 'onboarding_status')

    # Drop enum type
    sa.Enum(name='onboarding_status_enum').drop(op.get_bind(), checkfirst=True)
