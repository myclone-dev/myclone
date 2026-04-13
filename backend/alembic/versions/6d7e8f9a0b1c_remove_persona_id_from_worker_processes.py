"""remove persona_id from worker_processes

Revision ID: 6d7e8f9a0b1c
Revises: 5c1c221ad132
Create Date: 2025-09-24 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6d7e8f9a0b1c'
down_revision: Union[str, Sequence[str], None] = '5c1c221ad132'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove persona_id from worker_processes table since single worker handles all personas"""
    # Drop the foreign key constraint first
    op.drop_constraint('worker_processes_persona_id_fkey', 'worker_processes', type_='foreignkey')
    
    # Drop the index
    op.drop_index('ix_worker_processes_persona_id', 'worker_processes')
    
    # Drop the column
    op.drop_column('worker_processes', 'persona_id')


def downgrade() -> None:
    """Add persona_id back to worker_processes table"""
    # Add the column back (nullable initially to avoid issues with existing rows)
    op.add_column('worker_processes', 
                  sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Create the index
    op.create_index('ix_worker_processes_persona_id', 'worker_processes', ['persona_id'])
    
    # Add the foreign key constraint back
    op.create_foreign_key('worker_processes_persona_id_fkey', 
                          'worker_processes', 'personas', 
                          ['persona_id'], ['id'])