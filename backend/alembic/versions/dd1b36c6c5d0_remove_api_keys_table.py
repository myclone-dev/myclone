"""remove_api_keys_table

Revision ID: dd1b36c6c5d0
Revises: 4dfc85d64fe1
Create Date: 2025-10-11 09:00:40.808829

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'dd1b36c6c5d0'
down_revision: Union[str, Sequence[str], None] = '4dfc85d64fe1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove api_keys table and apikeyscope enum."""
    # Drop the api_keys table
    op.drop_table('api_keys')

    # Drop the apikeyscope enum type
    op.execute('DROP TYPE IF EXISTS apikeyscope')


def downgrade() -> None:
    """Recreate api_keys table and apikeyscope enum."""
    # Recreate the enum type
    apikeyscope = postgresql.ENUM('BACKEND', 'FRONTEND', 'ADMIN', 'READ_ONLY', name='apikeyscope', create_type=False)
    apikeyscope.create(op.get_bind(), checkfirst=True)

    # Recreate the api_keys table
    op.create_table('api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key_hash', sa.String(length=255), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('scope', postgresql.ENUM('BACKEND', 'FRONTEND', 'ADMIN', 'READ_ONLY', name='apikeyscope', create_type=False), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
