"""merge heads: remove_free_pricing_model and add_webhook_to_personas

Revision ID: e1c8318813d9
Revises: 46218035de30, b1c2d3e4f5g6
Create Date: 2025-12-29 18:38:17.782266

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1c8318813d9'
down_revision: Union[str, Sequence[str], None] = ('46218035de30', 'b1c2d3e4f5g6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
