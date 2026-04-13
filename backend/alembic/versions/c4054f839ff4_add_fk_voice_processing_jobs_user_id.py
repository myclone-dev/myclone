"""add_fk_voice_processing_jobs_user_id

Revision ID: c4054f839ff4
Revises: 73ff81b886e3
Create Date: 2025-10-11 09:51:47.249731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4054f839ff4'
down_revision: Union[str, Sequence[str], None] = '73ff81b886e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change user_id from VARCHAR to UUID and add FK to users.id"""
    from sqlalchemy.dialects import postgresql

    # Drop the old VARCHAR user_id column
    op.drop_column('voice_processing_jobs', 'user_id')

    # Add new UUID user_id column with FK to users.id
    op.add_column('voice_processing_jobs',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True)
    )

    # Create foreign key constraint
    op.create_foreign_key(
        'fk_voice_processing_jobs_user_id',
        'voice_processing_jobs',
        'users',
        ['user_id'],
        ['id'],
        ondelete='SET NULL'  # Set to NULL if user is deleted
    )

    # Recreate the index
    op.create_index(
        op.f('ix_voice_processing_jobs_user_id'),
        'voice_processing_jobs',
        ['user_id'],
        unique=False
    )


def downgrade() -> None:
    """Revert user_id back to VARCHAR"""
    # Drop FK constraint
    op.drop_constraint('fk_voice_processing_jobs_user_id', 'voice_processing_jobs', type_='foreignkey')

    # Drop index
    op.drop_index(op.f('ix_voice_processing_jobs_user_id'), table_name='voice_processing_jobs')

    # Drop UUID column
    op.drop_column('voice_processing_jobs', 'user_id')

    # Restore VARCHAR column
    op.add_column('voice_processing_jobs',
        sa.Column('user_id', sa.String(length=255), nullable=True)
    )

    # Recreate index
    op.create_index(
        op.f('ix_voice_processing_jobs_user_id'),
        'voice_processing_jobs',
        ['user_id'],
        unique=False
    )
