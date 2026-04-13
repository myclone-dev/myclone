"""Add columns to persona_prompts table

Revision ID: f3b2c1a9d8e7
Revises: 6d7e8f9a0b1c
Create Date: 2025-09-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = 'f3b2c1a9d8e7'
down_revision: Union[str, Sequence[str], None] = '6d7e8f9a0b1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    """Add new columns to persona_prompts table"""
    op.add_column(
        'persona_prompts',
        sa.Column('prompt_template', sa.Text(), nullable=True),
    )
    op.add_column(
        'persona_prompts',
        sa.Column('example_prompt', sa.Text(), nullable=True),
    )
    op.add_column(
        'persona_prompts',
        sa.Column('is_dynamic', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )


def downgrade() -> None:
    """Remove the added columns from persona_prompts table"""
    op.drop_column('persona_prompts', 'is_dynamic')
    op.drop_column('persona_prompts', 'example_prompt')
    op.drop_column('persona_prompts', 'prompt_template')

