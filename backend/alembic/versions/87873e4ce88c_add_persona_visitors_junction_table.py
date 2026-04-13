"""add_persona_visitors_junction_table

Revision ID: 87873e4ce88c
Revises: 784cc803b8c2
Create Date: 2025-10-30 01:40:10.585212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '87873e4ce88c'
down_revision: Union[str, Sequence[str], None] = '784cc803b8c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create persona_visitors junction table (many-to-many relationship)
    op.create_table(
        'persona_visitors',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('persona_id', UUID(as_uuid=True), sa.ForeignKey('personas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('visitor_id', UUID(as_uuid=True), sa.ForeignKey('visitor_whitelist.id', ondelete='CASCADE'), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.UniqueConstraint('persona_id', 'visitor_id', name='uq_persona_visitors_persona_visitor'),
    )

    # Create indexes
    op.create_index('idx_persona_visitors_persona', 'persona_visitors', ['persona_id'])
    op.create_index('idx_persona_visitors_visitor', 'persona_visitors', ['visitor_id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_persona_visitors_visitor', table_name='persona_visitors')
    op.drop_index('idx_persona_visitors_persona', table_name='persona_visitors')

    # Drop table
    op.drop_table('persona_visitors')
