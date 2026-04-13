"""Merge migration branches

Revision ID: 301ca550b0cc
Revises: f3b2c1a9d8e7, 15fa73ba2dc4
Create Date: 2025-09-26 11:30:47.802505

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '301ca550b0cc'
down_revision: Union[str, Sequence[str], None] = ('f3b2c1a9d8e7', '15fa73ba2dc4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
