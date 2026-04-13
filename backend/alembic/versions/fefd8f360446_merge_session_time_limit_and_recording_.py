"""merge session_time_limit and recording_fields

Revision ID: fefd8f360446
Revises: 6b98f2f67c4c, d402ba7fae6c
Create Date: 2026-01-21 15:47:39.394375

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fefd8f360446'
down_revision: Union[str, Sequence[str], None] = ('6b98f2f67c4c', 'd402ba7fae6c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
