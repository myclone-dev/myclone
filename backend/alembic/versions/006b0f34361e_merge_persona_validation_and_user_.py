"""merge persona validation and user fields branches

Revision ID: 006b0f34361e
Revises: 5ee3980520ca, a532270ff166
Create Date: 2025-11-05 18:03:28.489170

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006b0f34361e'
down_revision: Union[str, Sequence[str], None] = ('5ee3980520ca', 'a532270ff166')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
