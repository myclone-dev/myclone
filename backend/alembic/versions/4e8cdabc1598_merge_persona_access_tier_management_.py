"""merge persona access, tier management, and unique constraint migrations

Revision ID: 4e8cdabc1598
Revises: 4f2b493172de, f5c76f37204d
Create Date: 2025-10-30 20:40:24.032609

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e8cdabc1598'
down_revision: Union[str, Sequence[str], None] = ('4f2b493172de', 'f5c76f37204d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
