"""add_voice_enabled_to_personas

Revision ID: 1d7355af2e26
Revises: 817ab2930dc3
Create Date: 2026-02-17 05:55:49.593126

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d7355af2e26'
down_revision: Union[str, Sequence[str], None] = '817ab2930dc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('personas', sa.Column('voice_enabled', sa.Boolean(), server_default='true', nullable=False, comment='Whether voice chat is enabled for this persona'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('personas', 'voice_enabled')
