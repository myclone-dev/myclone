"""merge suggested_questions and password_auth branches

Revision ID: 6a1d662be909
Revises: 2dd8da251a96, 57501ffb6332
Create Date: 2025-11-06 10:22:46.009999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a1d662be909'
down_revision: Union[str, Sequence[str], None] = ('2dd8da251a96', '57501ffb6332')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
