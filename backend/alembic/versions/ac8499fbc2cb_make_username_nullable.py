"""make_username_nullable

Revision ID: ac8499fbc2cb
Revises: 76067a8de74c
Create Date: 2025-10-08 22:21:45.791927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac8499fbc2cb'
down_revision: Union[str, Sequence[str], None] = '76067a8de74c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop unique constraint on username (will be recreated as partial index in next step)
    op.drop_constraint('uq_users_username', 'users', type_='unique')

    # Make username nullable
    op.alter_column('users', 'username',
                    existing_type=sa.Text(),
                    nullable=True)

    # Create partial unique index (only enforces uniqueness for non-null values)
    op.create_index(
        'uq_users_username_partial',
        'users',
        ['username'],
        unique=True,
        postgresql_where=sa.text('username IS NOT NULL')
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop partial unique index
    op.drop_index('uq_users_username_partial', table_name='users')

    # Make username non-nullable (will fail if there are null usernames)
    op.alter_column('users', 'username',
                    existing_type=sa.Text(),
                    nullable=False)

    # Recreate unique constraint
    op.create_unique_constraint('uq_users_username', 'users', ['username'])
