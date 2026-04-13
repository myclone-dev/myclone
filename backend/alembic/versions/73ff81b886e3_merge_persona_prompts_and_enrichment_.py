"""merge persona_prompts and enrichment migration branches

Revision ID: 73ff81b886e3
Revises: 92c24e05c5c3, dd1b36c6c5d0
Create Date: 2025-10-11 09:49:00.348255

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '73ff81b886e3'
down_revision: Union[str, Sequence[str], None] = ('92c24e05c5c3', 'dd1b36c6c5d0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
