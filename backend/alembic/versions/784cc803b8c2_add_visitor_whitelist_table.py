"""add_visitor_whitelist_table

Revision ID: 784cc803b8c2
Revises: 30e384eeba91
Create Date: 2025-10-30 01:39:00.969785

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '784cc803b8c2'
down_revision: Union[str, Sequence[str], None] = '30e384eeba91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create visitor_whitelist table (global user-level whitelist)
    op.create_table(
        'visitor_whitelist',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.UniqueConstraint('user_id', 'email', name='uq_visitor_whitelist_user_email'),
    )

    # Create indexes
    op.create_index('idx_visitor_whitelist_user', 'visitor_whitelist', ['user_id'])
    op.create_index('idx_visitor_whitelist_email', 'visitor_whitelist', ['user_id', 'email'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_visitor_whitelist_email', table_name='visitor_whitelist')
    op.drop_index('idx_visitor_whitelist_user', table_name='visitor_whitelist')

    # Drop table
    op.drop_table('visitor_whitelist')
