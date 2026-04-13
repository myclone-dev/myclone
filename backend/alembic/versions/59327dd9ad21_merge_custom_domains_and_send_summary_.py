"""merge custom_domains and send_summary_email heads

Revision ID: 59327dd9ad21
Revises: 762884925a90, d4e5f6g7h8i9
Create Date: 2025-12-24 11:55:06.433608

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59327dd9ad21'
down_revision: Union[str, Sequence[str], None] = ('762884925a90', 'd4e5f6g7h8i9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
