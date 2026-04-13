"""replace_persona_username_with_persona_id

Revision ID: 4dfc85d64fe1
Revises: 9cb443f845e7
Create Date: 2025-10-11 08:07:06.905014

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4dfc85d64fe1'
down_revision: Union[str, Sequence[str], None] = '9cb443f845e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ===== persona_prompts table =====
    # Add persona_id column with FK to personas.id
    op.add_column('persona_prompts',
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=False)
    )
    op.create_foreign_key(
        'fk_persona_prompts_persona_id',
        'persona_prompts',
        'personas',
        ['persona_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Drop unique constraint on persona_username
    op.drop_constraint('persona_prompts_persona_username_key', 'persona_prompts', type_='unique')

    # Drop persona_username column
    op.drop_column('persona_prompts', 'persona_username')

    # ===== persona_prompts_history table =====
    # Add persona_id column with FK to personas.id
    op.add_column('persona_prompts_history',
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=False)
    )
    op.create_foreign_key(
        'fk_persona_prompts_history_persona_id',
        'persona_prompts_history',
        'personas',
        ['persona_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Drop persona_username column
    op.drop_column('persona_prompts_history', 'persona_username')

    # ===== prompt_templates table =====
    # Add persona_id column with FK to personas.id
    op.add_column('prompt_templates',
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_prompt_templates_persona_id',
        'prompt_templates',
        'personas',
        ['persona_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Drop old unique constraint that includes persona_username
    op.drop_constraint('uq_prompt_template_unique_active', 'prompt_templates', type_='unique')

    # Drop persona_username column
    op.drop_column('prompt_templates', 'persona_username')

    # Re-create unique constraint with persona_id instead of persona_username
    op.create_unique_constraint(
        'uq_prompt_template_unique_active',
        'prompt_templates',
        ['type', 'expertise', 'persona_id', 'platform', 'is_active']
    )


def downgrade() -> None:
    """Downgrade schema."""

    # ===== prompt_templates table =====
    # Drop new unique constraint
    op.drop_constraint('uq_prompt_template_unique_active', 'prompt_templates', type_='unique')

    # Add persona_username column back
    op.add_column('prompt_templates',
        sa.Column('persona_username', sa.VARCHAR(length=100), nullable=True)
    )

    # Drop FK and persona_id column
    op.drop_constraint('fk_prompt_templates_persona_id', 'prompt_templates', type_='foreignkey')
    op.drop_column('prompt_templates', 'persona_id')

    # Re-create old unique constraint with persona_username
    op.create_unique_constraint(
        'uq_prompt_template_unique_active',
        'prompt_templates',
        ['type', 'expertise', 'persona_username', 'platform', 'is_active']
    )

    # ===== persona_prompts_history table =====
    # Add persona_username column back
    op.add_column('persona_prompts_history',
        sa.Column('persona_username', sa.VARCHAR(length=100), nullable=False)
    )

    # Drop FK and persona_id column
    op.drop_constraint('fk_persona_prompts_history_persona_id', 'persona_prompts_history', type_='foreignkey')
    op.drop_column('persona_prompts_history', 'persona_id')

    # ===== persona_prompts table =====
    # Add persona_username column back
    op.add_column('persona_prompts',
        sa.Column('persona_username', sa.VARCHAR(length=100), nullable=False)
    )

    # Re-create unique constraint on persona_username
    op.create_unique_constraint('persona_prompts_persona_username_key', 'persona_prompts', ['persona_username'])

    # Drop FK and persona_id column
    op.drop_constraint('fk_persona_prompts_persona_id', 'persona_prompts', type_='foreignkey')
    op.drop_column('persona_prompts', 'persona_id')
