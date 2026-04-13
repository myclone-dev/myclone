"""add_persona_access_control_is_private

Revision ID: 30e384eeba91
Revises: 22883c686f45
Create Date: 2025-10-30 01:37:19.586955

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30e384eeba91'
down_revision: Union[str, Sequence[str], None] = '22883c686f45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_private column to personas table (default: False - all personas public by default)
    op.add_column('personas', sa.Column('is_private', sa.Boolean(), server_default='false', nullable=False))

    # Add timestamp for when access control was enabled
    op.add_column('personas', sa.Column('access_control_enabled_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove access control columns
    op.drop_column('personas', 'access_control_enabled_at')
    op.drop_column('personas', 'is_private')
