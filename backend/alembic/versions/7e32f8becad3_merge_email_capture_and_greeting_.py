"""merge email capture and greeting branches

Revision ID: 7e32f8becad3
Revises: 1a2b3c4d5e6f, af1be64edbb7
Create Date: 2025-11-24 21:50:26.349672

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e32f8becad3'
down_revision: Union[str, Sequence[str], None] = ('1a2b3c4d5e6f', 'af1be64edbb7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
