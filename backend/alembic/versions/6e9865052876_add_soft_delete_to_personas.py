"""add_soft_delete_to_personas

Revision ID: 6e9865052876
Revises: 4e8cdabc1598
Create Date: 2025-10-31 20:21:29.417606

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e9865052876'
down_revision: Union[str, Sequence[str], None] = '4e8cdabc1598'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_active column (default: true - all existing personas are active)
    op.add_column('personas', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))

    # Add deleted_at column (tracks when persona was soft deleted)
    op.add_column('personas', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    # Add index on is_active for efficient filtering
    op.create_index('idx_personas_is_active', 'personas', ['is_active'])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove index and columns
    op.drop_index('idx_personas_is_active', table_name='personas')
    op.drop_column('personas', 'deleted_at')
    op.drop_column('personas', 'is_active')
