"""drop_external_data_sources_table

Revision ID: 5ba7eefcbec1
Revises: 3fefbcb279b7
Create Date: 2025-10-14 00:13:07.290551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5ba7eefcbec1'
down_revision: Union[str, Sequence[str], None] = '3fefbcb279b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop external_data_sources table - replaced by persona_data_sources and normalized tables."""
    # Drop the external_data_sources table
    op.drop_table('external_data_sources')


def downgrade() -> None:
    """Recreate external_data_sources table for rollback."""
    # Recreate the external_data_sources table with original schema
    op.create_table(
        'external_data_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('data_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
