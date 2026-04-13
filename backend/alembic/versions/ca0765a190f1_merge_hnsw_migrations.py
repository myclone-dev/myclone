"""merge_hnsw_migrations

Revision ID: ca0765a190f1
Revises: 6b36ed7a194f, c7365969ce1a
Create Date: 2025-10-01 20:40:38.836961

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca0765a190f1'
down_revision: Union[str, Sequence[str], None] = ('6b36ed7a194f', 'c7365969ce1a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
