"""merge workflow and llm expertise heads

Revision ID: cecbbd8a90eb
Revises: 132600cde686, b2c3d4e5f6g8
Create Date: 2025-12-11 00:03:52.680696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cecbbd8a90eb'
down_revision: Union[str, Sequence[str], None] = ('132600cde686', 'b2c3d4e5f6g8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
