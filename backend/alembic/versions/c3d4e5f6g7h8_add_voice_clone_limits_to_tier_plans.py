"""add_voice_clone_limits_to_tier_plans

Revision ID: c3d4e5f6g7h8
Revises: aae4332f133e
Create Date: 2025-12-16 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"
down_revision: Union[str, Sequence[str], None] = "aae4332f133e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add voice clone limits to tier_plans table.

    Voice clone limits per tier (all use Cartesia):
    - Free (0): 1 voice clone
    - Pro (1): 1 voice clone
    - Business (2): 3 voice clones
    - Enterprise (3): Unlimited (-1)
    """
    # Check if column already exists
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("tier_plans")]

    if "max_voice_clones" not in columns:
        # Add the max_voice_clones column
        op.add_column(
            "tier_plans",
            sa.Column(
                "max_voice_clones",
                sa.Integer(),
                nullable=False,
                server_default="1",
                comment="Max voice clones (-1 = unlimited)",
            ),
        )

    # Update tier limits (all tiers use Cartesia)
    op.execute(
        """
        UPDATE tier_plans SET max_voice_clones = CASE
            WHEN id = 0 THEN 1   -- Free: 1 voice clone
            WHEN id = 1 THEN 1   -- Pro: 1 voice clone
            WHEN id = 2 THEN 3   -- Business: 3 voice clones
            WHEN id = 3 THEN -1  -- Enterprise: unlimited
            ELSE 1               -- Default: 1
        END
    """
    )


def downgrade() -> None:
    """Remove voice clone limits from tier_plans"""
    op.drop_column("tier_plans", "max_voice_clones")
