"""add worker processes and active rooms tables

Revision ID: 5c1c221ad132
Revises: 0e763f7538c0
Create Date: 2025-09-23 18:58:30.549494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5c1c221ad132'
down_revision: Union[str, Sequence[str], None] = '0e763f7538c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum type for worker state using raw SQL to avoid SQLAlchemy auto-creation
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE worker_state_enum AS ENUM ('starting', 'healthy', 'idle', 'terminated');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))
    
    # Create worker_processes table (if it doesn't exist)
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS worker_processes (
            id SERIAL PRIMARY KEY,
            persona_id UUID NOT NULL REFERENCES personas(id),
            pid INTEGER NOT NULL,
            port INTEGER NOT NULL UNIQUE,
            agent_name VARCHAR(100) NOT NULL UNIQUE,
            state worker_state_enum NOT NULL DEFAULT 'starting',
            started_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
            last_health_check TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
            last_activity TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
            active_jobs INTEGER DEFAULT 0 NOT NULL,
            health_status JSON DEFAULT '{}' NOT NULL
        )
    """))
    
    # Skip the op.create_table approach and create indexes manually
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_worker_processes_persona_id ON worker_processes(persona_id)"))
    
    # Create active_rooms table (if it doesn't exist)
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS active_rooms (
            room_name VARCHAR(255) PRIMARY KEY,
            worker_id INTEGER NOT NULL REFERENCES worker_processes(id) ON DELETE CASCADE,
            persona_id UUID NOT NULL REFERENCES personas(id),
            user_id VARCHAR NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
            last_activity TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
        )
    """))
    
    # Create indexes for active_rooms
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_active_rooms_worker_id ON active_rooms(worker_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_active_rooms_persona_id ON active_rooms(persona_id)"))


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes for active_rooms
    op.drop_index('ix_active_rooms_persona_id', 'active_rooms')
    op.drop_index('ix_active_rooms_worker_id', 'active_rooms')
    
    # Drop active_rooms table
    op.drop_table('active_rooms')
    
    # Drop indexes for worker_processes
    op.drop_index('ix_worker_processes_persona_id', 'worker_processes')
    
    # Drop worker_processes table
    op.drop_table('worker_processes')
    
    # Drop enum type
    postgresql.ENUM(name='worker_state_enum').drop(op.get_bind())
