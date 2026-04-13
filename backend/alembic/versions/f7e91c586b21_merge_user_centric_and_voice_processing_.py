"""merge user_centric and voice_processing branches

Revision ID: f7e91c586b21
Revises: 9bae0bf3172e, ad10d18071d1
Create Date: 2025-10-08 00:34:57.311929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7e91c586b21'
down_revision: Union[str, Sequence[str], None] = ('9bae0bf3172e', 'ad10d18071d1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
