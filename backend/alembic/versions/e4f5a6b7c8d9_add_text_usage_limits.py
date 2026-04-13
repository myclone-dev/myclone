"""add_text_usage_limits

Revision ID: e4f5a6b7c8d9
Revises: d3e148d9e454
Create Date: 2025-12-26 00:00:00.000000

Adds text chat usage limits per tier and tracking columns:
- max_text_messages_per_month to tier_plans
- text_messages_used and text_usage_reset_at to user_usage_cache

Text usage is charged to the PERSONA OWNER, not the visitor.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "e1c8318813d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add text usage limits to tier_plans and tracking columns to user_usage_cache.

    Text messages per tier (monthly, resets at billing cycle):
    - Free (0): 500 messages
    - Pro (1): 10,000 messages
    - Business (2): 40,000 messages
    - Enterprise (3): Unlimited (-1)

    Usage is charged to the PERSONA OWNER when anyone chats with their persona.
    """
    conn = op.get_bind()
    inspector = inspect(conn)

    # ============================================
    # 1. Add max_text_messages_per_month to tier_plans
    # ============================================
    tier_columns = [col["name"] for col in inspector.get_columns("tier_plans")]

    if "max_text_messages_per_month" not in tier_columns:
        op.add_column(
            "tier_plans",
            sa.Column(
                "max_text_messages_per_month",
                sa.Integer(),
                nullable=False,
                server_default="500",
                comment="Max text chat messages per month (-1 = unlimited)",
            ),
        )

    # Update tier limits
    op.execute(
        """
        UPDATE tier_plans SET max_text_messages_per_month = CASE
            WHEN id = 0 THEN 500     -- Free: 500 messages
            WHEN id = 1 THEN 10000   -- Pro: 10,000 messages
            WHEN id = 2 THEN 40000   -- Business: 40,000 messages
            WHEN id = 3 THEN -1      -- Enterprise: unlimited
            ELSE 500                 -- Default: 500 messages
        END
    """
    )

    # ============================================
    # 2. Add text tracking to user_usage_cache
    # ============================================
    usage_columns = [col["name"] for col in inspector.get_columns("user_usage_cache")]

    if "text_messages_used" not in usage_columns:
        op.add_column(
            "user_usage_cache",
            sa.Column(
                "text_messages_used",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
                comment="Text chat messages used in current period",
            ),
        )

    if "text_usage_reset_at" not in usage_columns:
        op.add_column(
            "user_usage_cache",
            sa.Column(
                "text_usage_reset_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="When text usage resets (monthly)",
            ),
        )


def downgrade() -> None:
    """Remove text usage limits and tracking columns."""
    # Remove columns from user_usage_cache
    op.drop_column("user_usage_cache", "text_usage_reset_at")
    op.drop_column("user_usage_cache", "text_messages_used")

    # Remove column from tier_plans
    op.drop_column("tier_plans", "max_text_messages_per_month")
