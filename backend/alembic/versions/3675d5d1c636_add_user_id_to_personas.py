"""add_user_id_to_personas

Revision ID: 3675d5d1c636
Revises: de2129922b52
Create Date: 2025-10-07 19:27:42.123456

This migration modifies the existing personas table to add user_id column.
This is a BREAKING CHANGE that enables the user-centric data model.

IMPORTANT:
- The user_id column is NOT NULL (required for all personas)
- All new personas MUST have a user_id
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3675d5d1c636'
down_revision: Union[str, Sequence[str], None] = 'de2129922b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user_id column to personas table."""

    # Add user_id column as NOT NULL (required for all personas)
    op.add_column(
        'personas',
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment='User who owns this persona - enables multiple personas per user'
        )
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_personas_user_id',
        'personas',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Create index for user_id lookups
    op.create_index('idx_personas_user_id', 'personas', ['user_id'])


def downgrade() -> None:
    """Remove user_id column from personas table."""

    # Drop index first
    op.drop_index('idx_personas_user_id', table_name='personas')

    # Drop foreign key constraint
    op.drop_constraint('fk_personas_user_id', 'personas', type_='foreignkey')

    # Drop column
    op.drop_column('personas', 'user_id')
