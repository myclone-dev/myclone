"""add_greeting_message_to_personas

Revision ID: 6833bf0ae573
Revises: ff75d8a68c38
Create Date: 2025-11-21 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6833bf0ae573'
down_revision: Union[str, Sequence[str], None] = 'ff75d8a68c38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add greeting_message column to personas table."""
    op.add_column('personas', sa.Column('greeting_message', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove greeting_message column from personas table."""
    op.drop_column('personas', 'greeting_message')
