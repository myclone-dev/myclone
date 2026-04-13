"""remove_changed_at_from_persona_prompts_history

Revision ID: 30de497b1ee0
Revises: 5ba7eefcbec1
Create Date: 2025-10-14 20:40:32.296839

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30de497b1ee0'
down_revision: Union[str, Sequence[str], None] = '5ba7eefcbec1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Remove changed_at column and its index from persona_prompts_history.

    The changed_at field is redundant - we can use created_at instead since it captures
    the timestamp when the history entry was created (i.e., when the version was archived).

    For existing records, created_at will be set to changed_at value where created_at is NULL.
    """
    # Step 1: Update any NULL created_at values to use changed_at value
    # (For existing records, created_at might be NULL or have the original prompt's creation time)
    op.execute("""
        UPDATE persona_prompts_history
        SET created_at = changed_at
        WHERE created_at IS NULL
    """)

    # Step 2: Make created_at NOT NULL with default
    op.alter_column('persona_prompts_history', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.text('CURRENT_TIMESTAMP'))

    # Step 3: Drop index
    op.drop_index('ix_persona_prompts_history_changed_at', table_name='persona_prompts_history', if_exists=True)

    # Step 4: Drop column
    op.drop_column('persona_prompts_history', 'changed_at')


def downgrade() -> None:
    """Downgrade schema: Re-add changed_at column and its index."""
    from sqlalchemy.dialects import postgresql

    # Step 1: Add changed_at column back (temporarily nullable)
    op.add_column('persona_prompts_history',
        sa.Column('changed_at', postgresql.TIMESTAMP(timezone=True), nullable=True)
    )

    # Step 2: Populate changed_at with created_at values
    op.execute("""
        UPDATE persona_prompts_history
        SET changed_at = created_at
    """)

    # Step 3: Make changed_at NOT NULL
    op.alter_column('persona_prompts_history', 'changed_at',
                    existing_type=postgresql.TIMESTAMP(timezone=True),
                    nullable=False)

    # Step 4: Make created_at nullable again and remove default
    op.alter_column('persona_prompts_history', 'created_at',
                    existing_type=postgresql.TIMESTAMP(timezone=True),
                    nullable=True,
                    server_default=None)

    # Step 5: Recreate index
    op.create_index('ix_persona_prompts_history_changed_at', 'persona_prompts_history', ['changed_at'], unique=False)
