"""add_unique_constraint_persona_prompts_active

Revision ID: f5c76f37204d
Revises: 272ec6abd141
Create Date: 2025-10-30 18:12:13.355738

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5c76f37204d'
down_revision: Union[str, Sequence[str], None] = '272ec6abd141'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Before creating the constraint, ensure no duplicate active prompts exist
    # Set all but the most recent active prompt per persona to inactive
    op.execute("""
        WITH ranked_prompts AS (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY persona_id ORDER BY created_at DESC) as rn
            FROM persona_prompts
            WHERE is_active = true
        )
        UPDATE persona_prompts
        SET is_active = false
        WHERE id IN (
            SELECT id FROM ranked_prompts WHERE rn > 1
        )
    """)
    
    # Create the partial unique index for active prompts
    op.create_index(
        'uq_persona_prompts_active',
        'persona_prompts',
        ['persona_id', 'is_active'],
        unique=True,
        postgresql_where=sa.text('is_active = true')
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the partial unique index
    op.drop_index('uq_persona_prompts_active', table_name='persona_prompts')

