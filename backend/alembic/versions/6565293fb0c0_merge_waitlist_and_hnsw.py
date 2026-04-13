"""merge_waitlist_and_hnsw

Revision ID: 6565293fb0c0
Revises: 7c8d9e0f1a2b, ca0765a190f1
Create Date: 2025-10-02 21:16:09.031718

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6565293fb0c0'
down_revision: Union[str, Sequence[str], None] = ('7c8d9e0f1a2b', 'ca0765a190f1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
