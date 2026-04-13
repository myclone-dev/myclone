"""merge migration branches

Revision ID: c4f54eb94991
Revises: 22af6d89f8de, b426ae7098dd
Create Date: 2026-01-28 04:09:06.827852

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f54eb94991'
down_revision: Union[str, Sequence[str], None] = ('22af6d89f8de', 'b426ae7098dd')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
