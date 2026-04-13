"""merge embeddings and prompt_template branches

Revision ID: 1ecf868eb955
Revises: 1e15f11578ab, db12a58b4eae
Create Date: 2025-10-15 01:14:45.872935

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ecf868eb955'
down_revision: Union[str, Sequence[str], None] = ('1e15f11578ab', 'db12a58b4eae')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
