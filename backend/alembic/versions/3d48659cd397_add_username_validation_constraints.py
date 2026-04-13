"""add_username_validation_constraints

Revision ID: 3d48659cd397
Revises: 208bcc9088c5
Create Date: 2025-11-14 20:30:03.996438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d48659cd397'
down_revision: Union[str, Sequence[str], None] = '208bcc9088c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add username validation constraints."""
    # Step 1: Normalize (lowercase, replace spaces with hyphens)
    op.execute("""
        UPDATE users
        SET username = LOWER(REPLACE(username, ' ', '-'))
        WHERE username IS NOT NULL
          AND (username != LOWER(username) OR username LIKE '% %');
    """)

    # Step 2: Lowercase constraint
    op.create_check_constraint(
        "username_lowercase_check",
        "users",
        "username IS NULL OR username = LOWER(username)",
    )

    # Step 3: Format constraint (start with letter, 3-30 chars total, allow letters/numbers/_/-)
    op.create_check_constraint(
        "username_format_check",
        "users",
        "username IS NULL OR username ~ '^[a-z][a-z0-9_-]{2,29}$'",
    )


def downgrade() -> None:
    """Remove username validation constraints."""
    op.drop_constraint("username_format_check", "users", type_="check")
    op.drop_constraint("username_lowercase_check", "users", type_="check")
