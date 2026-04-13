"""merge multiple heads

Revision ID: 6799ef3448b0
Revises: 1aa7dbeebdfb, 7df6a751b3c0
Create Date: 2026-01-26 10:39:25.423677

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6799ef3448b0'
down_revision: Union[str, Sequence[str], None] = ('1aa7dbeebdfb', '7df6a751b3c0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
