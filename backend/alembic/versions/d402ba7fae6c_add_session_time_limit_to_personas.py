"""add_session_time_limit_to_personas

Revision ID: d402ba7fae6c
Revises: 5fe416725809
Create Date: 2026-01-19 05:39:44.609495

Adds session time limit settings to personas table for visitor session management.
Creators can configure:
- session_time_limit_enabled: Whether time limits are enforced
- session_time_limit_minutes: Maximum session duration (default: 30 minutes)
- session_time_limit_warning_minutes: Warning before limit (default: 2 minutes)

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d402ba7fae6c"
down_revision: Union[str, Sequence[str], None] = "5fe416725809"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add session time limit columns to personas table."""
    # Enable/disable session time limits
    op.add_column(
        "personas",
        sa.Column(
            "session_time_limit_enabled",
            sa.Boolean(),
            server_default="false",
            nullable=False,
            comment="Whether session time limits are enforced for visitors",
        ),
    )

    # Maximum session duration in minutes (supports fractions like 2.5 for 2m 30s)
    op.add_column(
        "personas",
        sa.Column(
            "session_time_limit_minutes",
            sa.Float(),
            server_default="30.0",
            nullable=False,
            comment="Maximum session duration in minutes (default: 30, supports fractions like 2.5 for 2m 30s)",
        ),
    )

    # Warning time before session ends (supports fractions like 0.5 for 30s)
    op.add_column(
        "personas",
        sa.Column(
            "session_time_limit_warning_minutes",
            sa.Float(),
            server_default="2.0",
            nullable=False,
            comment="Minutes before limit to show warning (supports fractions like 0.5 for 30s)",
        ),
    )


def downgrade() -> None:
    """Remove session time limit columns from personas table."""
    op.drop_column("personas", "session_time_limit_warning_minutes")
    op.drop_column("personas", "session_time_limit_minutes")
    op.drop_column("personas", "session_time_limit_enabled")
