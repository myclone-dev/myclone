"""set_default_auto_for_language_column

Revision ID: 5d278baa5ef0
Revises: 48accb79d506
Create Date: 2026-01-15 16:45:24.043520

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d278baa5ef0'
down_revision: Union[str, Sequence[str], None] = '48accb79d506'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Set default value 'auto' for language column in personas table.
    
    This migration:
    1. Sets the default value to 'auto' for the language column
    2. Updates the column comment to reflect the new default
    3. Updates existing NULL values to 'auto' for consistency

    Note: Column remains nullable to support explicit NULL if needed,
    but new rows will default to 'auto' and NULL is semantically treated as 'auto'.
    """
    # Set server default to 'auto' and update comment
    op.alter_column(
        'personas',
        'language',
        server_default='auto',
        comment="Language code for persona responses (auto, en, hi, es, fr, zh, de, ar, it). NULL=auto, default='auto'",
        existing_type=sa.String(10),
        existing_nullable=True,
    )
    
    # Update existing NULL values to 'auto' for consistency
    # This ensures all personas have an explicit language value
    op.execute("UPDATE personas SET language = 'auto' WHERE language IS NULL")


def downgrade() -> None:
    """Remove default value from language column and restore original comment."""
    # Remove server default and restore original comment
    op.alter_column(
        'personas',
        'language',
        server_default=None,
        comment='Language code for persona responses (auto, en, hi, es, fr, zh, de, ar, it). NULL=auto',
        existing_type=sa.String(10),
        existing_nullable=True,
    )

