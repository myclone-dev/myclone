"""add_fk_persona_prompts_history_original_id

Revision ID: 9cb443f845e7
Revises: d4cd672073f2
Create Date: 2025-10-11 08:05:13.549273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9cb443f845e7'
down_revision: Union[str, Sequence[str], None] = 'd4cd672073f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add foreign key constraint from persona_prompts_history.original_id to persona_prompts.id
    op.create_foreign_key(
        'fk_persona_prompts_history_original_id',
        'persona_prompts_history',
        'persona_prompts',
        ['original_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove foreign key constraint
    op.drop_constraint(
        'fk_persona_prompts_history_original_id',
        'persona_prompts_history',
        type_='foreignkey'
    )
