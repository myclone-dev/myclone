"""add_strict_guideline_and_template_columns

Revision ID: 1bd75c734ca5
Revises: dda04d5cd0d5
Create Date: 2025-11-17 16:48:23.663445

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1bd75c734ca5'
down_revision: Union[str, Sequence[str], None] = 'dda04d5cd0d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add strict_guideline column to persona_prompts table
    op.add_column('persona_prompts', sa.Column('strict_guideline', sa.Text(), nullable=True))

    # Add strict_guideline column to persona_prompts_history table
    op.add_column('persona_prompts_history', sa.Column('strict_guideline', sa.Text(), nullable=True))

    # Add new columns to prompt_templates table
    op.add_column('prompt_templates', sa.Column('thinking_style', sa.Text(), nullable=True))
    op.add_column('prompt_templates', sa.Column('chat_objective', sa.Text(), nullable=True))
    op.add_column('prompt_templates', sa.Column('objective_response', sa.Text(), nullable=True))
    op.add_column('prompt_templates', sa.Column('response_structure', sa.Text(), nullable=True))
    op.add_column('prompt_templates', sa.Column('conversation_flow', sa.Text(), nullable=True))
    op.add_column('prompt_templates', sa.Column('strict_guideline', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns from prompt_templates table
    op.drop_column('prompt_templates', 'strict_guideline')
    op.drop_column('prompt_templates', 'conversation_flow')
    op.drop_column('prompt_templates', 'response_structure')
    op.drop_column('prompt_templates', 'objective_response')
    op.drop_column('prompt_templates', 'chat_objective')
    op.drop_column('prompt_templates', 'thinking_style')

    # Remove strict_guideline column from persona_prompts_history table
    op.drop_column('persona_prompts_history', 'strict_guideline')

    # Remove strict_guideline column from persona_prompts table
    op.drop_column('persona_prompts', 'strict_guideline')
