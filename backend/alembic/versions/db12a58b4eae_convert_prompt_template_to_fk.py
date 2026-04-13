"""convert_prompt_template_to_fk

Revision ID: db12a58b4eae
Revises: 30de497b1ee0
Create Date: 2025-10-14 21:19:07.512766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'db12a58b4eae'
down_revision: Union[str, Sequence[str], None] = '30de497b1ee0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert prompt_template Text field to prompt_template_id UUID FK.

    Changes:
    - Renames prompt_template → prompt_template_id in persona_prompts table
    - Renames prompt_template → prompt_template_id in persona_prompts_history table
    - Changes type from Text → UUID
    - Adds FK constraint to prompt_templates.id with SET NULL on delete
    - Adds index for query performance

    The old prompt_template field was dead code (never used in runtime).
    The new prompt_template_id tracks which template was used to generate the prompt.
    """

    # ===== persona_prompts table =====

    # Step 1: Add new prompt_template_id column (nullable, UUID, with comment)
    op.add_column('persona_prompts',
        sa.Column('prompt_template_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='FK to prompt_templates - tracks which template was used to generate this prompt')
    )

    # Step 2: Drop old prompt_template column (dead code - was never used)
    op.drop_column('persona_prompts', 'prompt_template')

    # Step 3: Add FK constraint to prompt_templates.id
    op.create_foreign_key(
        'fk_persona_prompts_template_id',
        'persona_prompts', 'prompt_templates',
        ['prompt_template_id'], ['id'],
        ondelete='SET NULL'
    )

    # Step 4: Add index for query performance (analytics, filtering)
    # Note: Index name matches SQLAlchemy's auto-generated convention: ix_{table}_{column}
    op.create_index(
        'ix_persona_prompts_prompt_template_id',
        'persona_prompts',
        ['prompt_template_id']
    )

    # ===== persona_prompts_history table =====

    # Step 1: Add new prompt_template_id column (nullable, UUID, with comment)
    op.add_column('persona_prompts_history',
        sa.Column('prompt_template_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='FK to prompt_templates - tracks which template was used')
    )

    # Step 2: Drop old prompt_template column
    op.drop_column('persona_prompts_history', 'prompt_template')

    # Step 3: Add FK constraint to prompt_templates.id
    op.create_foreign_key(
        'fk_persona_prompts_history_template_id',
        'persona_prompts_history', 'prompt_templates',
        ['prompt_template_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Revert prompt_template_id FK back to prompt_template Text field."""

    # ===== persona_prompts_history table =====

    # Step 1: Drop FK constraint
    op.drop_constraint('fk_persona_prompts_history_template_id', 'persona_prompts_history', type_='foreignkey')

    # Step 2: Drop prompt_template_id column
    op.drop_column('persona_prompts_history', 'prompt_template_id')

    # Step 3: Re-add old prompt_template Text column
    op.add_column('persona_prompts_history',
        sa.Column('prompt_template', sa.Text(), nullable=True)
    )

    # ===== persona_prompts table =====

    # Step 1: Drop index
    op.drop_index('ix_persona_prompts_prompt_template_id', table_name='persona_prompts')

    # Step 2: Drop FK constraint
    op.drop_constraint('fk_persona_prompts_template_id', 'persona_prompts', type_='foreignkey')

    # Step 3: Drop prompt_template_id column
    op.drop_column('persona_prompts', 'prompt_template_id')

    # Step 4: Re-add old prompt_template Text column
    op.add_column('persona_prompts',
        sa.Column('prompt_template', sa.Text(), nullable=True)
    )
