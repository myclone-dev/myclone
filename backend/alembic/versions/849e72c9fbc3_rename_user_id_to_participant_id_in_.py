"""rename_user_id_to_participant_id_in_active_rooms

Revision ID: 849e72c9fbc3
Revises: c9d793229de0
Create Date: 2025-10-11 07:31:55.509015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '849e72c9fbc3'
down_revision: Union[str, Sequence[str], None] = 'c9d793229de0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename user_id to participant_id in active_rooms table
    # This field stores LiveKit participant identifiers, not FK references to users table
    op.alter_column('active_rooms', 'user_id',
                    new_column_name='participant_id')


def downgrade() -> None:
    """Downgrade schema."""
    # Rename participant_id back to user_id
    op.alter_column('active_rooms', 'participant_id',
                    new_column_name='user_id')
