"""rename_persona_username_to_persona_name_with_composite_unique

Revision ID: c9d793229de0
Revises: ac8499fbc2cb
Create Date: 2025-10-09 00:32:57.222629

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d793229de0'
down_revision: Union[str, Sequence[str], None] = 'ac8499fbc2cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop unique constraint on username (SQLAlchemy auto-generates constraint name)
    op.drop_constraint('personas_username_key', 'personas', type_='unique')

    # Rename column from username to persona_name with default value
    op.alter_column('personas', 'username',
                    new_column_name='persona_name',
                    server_default='default')

    # Add composite unique constraint on (user_id, persona_name)
    op.create_unique_constraint(
        'uq_personas_user_persona_name',
        'personas',
        ['user_id', 'persona_name']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop composite unique constraint
    op.drop_constraint('uq_personas_user_persona_name', 'personas', type_='unique')

    # Rename column back to username
    op.alter_column('personas', 'persona_name', new_column_name='username')

    # Recreate unique constraint on username
    op.create_unique_constraint('personas_username_key', 'personas', ['username'])
