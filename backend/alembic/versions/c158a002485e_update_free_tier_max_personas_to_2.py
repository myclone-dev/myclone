"""update_free_tier_max_personas_to_2

Revision ID: c158a002485e
Revises: eb90ee4c0a06
Create Date: 2026-01-10 12:00:00.000000

Updates free tier (ID=0) max_personas from 1 to 2.
This allows free tier users to have 1 default persona + 1 custom persona.

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c158a002485e"
down_revision: Union[str, Sequence[str], None] = "eb90ee4c0a06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Update free tier (ID=0) to allow 2 personas instead of 1
    op.execute(sa.text("UPDATE tier_plans SET max_personas = 2 WHERE id = 0"))


def downgrade() -> None:
    """Downgrade schema."""
    # Revert free tier back to 1 persona
    op.execute(sa.text("UPDATE tier_plans SET max_personas = 1 WHERE id = 0"))
