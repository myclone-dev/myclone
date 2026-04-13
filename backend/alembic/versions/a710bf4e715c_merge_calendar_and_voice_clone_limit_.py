"""merge calendar and voice clone limit heads

Revision ID: a710bf4e715c
Revises: 8ae658a9d81f, c3d4e5f6g7h8
Create Date: 2025-12-20 19:15:52.834251

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a710bf4e715c'
down_revision: Union[str, Sequence[str], None] = ('8ae658a9d81f', 'c3d4e5f6g7h8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
