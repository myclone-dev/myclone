"""add_persona_name_validation_constraint

Revision ID: 5ee3980520ca
Revises: 174efc03f2f3
Create Date: 2025-11-04 10:04:10.131265

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ee3980520ca'
down_revision: Union[str, Sequence[str], None] = '174efc03f2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CHECK constraint for persona_name validation.

    Enforces:
    - Must start with a letter (not a number)
    - Length: 3-60 characters
    - Format: lowercase alphanumeric + hyphens
    - No leading/trailing/consecutive hyphens
    - Pattern: ^[a-z][a-z0-9]*(-[a-z0-9]+)*$

    Data Migration:
    - Finds personas starting with numbers (e.g., "666-persona", "2024-sales")
    - Prepends "persona-" to fix them (e.g., "persona-666-persona", "persona-2024-sales")
    """
    # Step 1: Fix existing personas that start with numbers
    # This ensures all existing data conforms to the new constraint
    op.execute(
        """
        UPDATE personas
        SET persona_name = 'persona-' || persona_name
        WHERE persona_name ~ '^[0-9]'
        """
    )

    # Step 2: Add the CHECK constraint
    # Now that all data is valid, we can safely add the constraint
    op.execute(
        """
        ALTER TABLE personas
        ADD CONSTRAINT check_persona_name_format
        CHECK (
            persona_name ~ '^[a-z][a-z0-9]*(-[a-z0-9]+)*$'
            AND length(persona_name) >= 3
            AND length(persona_name) <= 60
        )
        """
    )


def downgrade() -> None:
    """Remove CHECK constraint for persona_name validation."""
    op.execute(
        """
        ALTER TABLE personas
        DROP CONSTRAINT IF EXISTS check_persona_name_format
        """
    )
