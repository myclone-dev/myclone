"""merge persona access control and tier management migrations

Revision ID: 4f2b493172de
Revises: 272ec6abd141, ff75d8a68c38
Create Date: 2025-10-30 19:02:45.165555

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f2b493172de'
down_revision: Union[str, Sequence[str], None] = ('272ec6abd141', 'ff75d8a68c38')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
