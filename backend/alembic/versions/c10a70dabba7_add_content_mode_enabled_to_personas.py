"""add content_mode_enabled to personas

Revision ID: c10a70dabba7
Revises: 1d7355af2e26
Create Date: 2026-02-19 22:16:28.820507

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c10a70dabba7'
down_revision: Union[str, Sequence[str], None] = '1d7355af2e26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('personas', sa.Column('content_mode_enabled', sa.Boolean(), server_default='false', nullable=False, comment='Whether content creation mode is enabled for this persona'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('personas', 'content_mode_enabled')
