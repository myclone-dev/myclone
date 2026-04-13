"""merge_timezone_and_voice_processing_migrations

Revision ID: 9bae0bf3172e
Revises: 807c772784b4, ab5934b24d71
Create Date: 2025-10-06 17:52:15.837340

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bae0bf3172e'
down_revision: Union[str, Sequence[str], None] = ('807c772784b4', 'ab5934b24d71')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
