"""add_voice_usage_limits

Revision ID: d3e148d9e454
Revises: 59327dd9ad21
Create Date: 2025-12-23 00:00:00.000000

Adds voice usage limits per tier and tracking tables:
- max_voice_minutes_per_month to tier_plans
- voice_seconds_used and voice_usage_reset_at to user_usage_cache
- voice_sessions table for tracking individual calls (owner-based)

Voice usage is charged to the PERSONA OWNER, not the caller.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "d3e148d9e454"
down_revision: Union[str, Sequence[str], None] = "59327dd9ad21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add voice usage limits to tier_plans and create tracking tables.

    Voice minutes per tier (monthly, resets at billing cycle):
    - Free (0): 10 minutes
    - Pro (1): 100 minutes
    - Business (2): 400 minutes
    - Enterprise (3): Unlimited (-1)

    Usage is charged to the PERSONA OWNER when anyone calls their persona.
    """
    conn = op.get_bind()
    inspector = inspect(conn)

    # ============================================
    # 1. Add max_voice_minutes_per_month to tier_plans
    # ============================================
    tier_columns = [col["name"] for col in inspector.get_columns("tier_plans")]

    if "max_voice_minutes_per_month" not in tier_columns:
        op.add_column(
            "tier_plans",
            sa.Column(
                "max_voice_minutes_per_month",
                sa.Integer(),
                nullable=False,
                server_default="10",
                comment="Max voice chat minutes per month (-1 = unlimited)",
            ),
        )

    # Update tier limits
    op.execute(
        """
        UPDATE tier_plans SET max_voice_minutes_per_month = CASE
            WHEN id = 0 THEN 10    -- Free: 10 minutes
            WHEN id = 1 THEN 100   -- Pro: 100 minutes
            WHEN id = 2 THEN 400   -- Business: 400 minutes
            WHEN id = 3 THEN -1    -- Enterprise: unlimited
            ELSE 10                -- Default: 10 minutes
        END
    """
    )

    # ============================================
    # 2. Add voice tracking to user_usage_cache
    # ============================================
    usage_columns = [col["name"] for col in inspector.get_columns("user_usage_cache")]

    if "voice_seconds_used" not in usage_columns:
        op.add_column(
            "user_usage_cache",
            sa.Column(
                "voice_seconds_used",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
                comment="Voice chat seconds used in current period",
            ),
        )

    if "voice_usage_reset_at" not in usage_columns:
        op.add_column(
            "user_usage_cache",
            sa.Column(
                "voice_usage_reset_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="When voice usage resets (monthly)",
            ),
        )

    # ============================================
    # 3. Create voice_session_status enum
    # ============================================
    # Check if enum exists first
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'voice_session_status_enum'")
    )
    enum_exists = result.fetchone() is not None

    if not enum_exists:
        # Create enum type manually before creating table
        op.execute(
            """
            CREATE TYPE voice_session_status_enum AS ENUM (
                'active',
                'completed',
                'limit_exceeded',
                'disconnected',
                'timeout'
            )
            """
        )

    # Use existing enum type in table creation (don't try to create it again)
    # Use postgresql.ENUM with create_type=False to reference existing type
    voice_session_status_enum = postgresql.ENUM(
        "active",
        "completed",
        "limit_exceeded",
        "disconnected",
        "timeout",
        name="voice_session_status_enum",
        create_type=False,  # Important: Don't try to create the type again
    )

    # ============================================
    # 4. Create voice_sessions table (owner-centric)
    # ============================================
    if "voice_sessions" not in inspector.get_table_names():
        op.create_table(
            "voice_sessions",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "persona_id",
                UUID(as_uuid=True),
                sa.ForeignKey("personas.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "persona_owner_id",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                comment="Persona owner whose quota is consumed",
            ),
            sa.Column(
                "caller_session_token",
                sa.String(255),
                nullable=True,
                comment="Caller session token (for analytics only)",
            ),
            sa.Column(
                "room_name",
                sa.String(255),
                nullable=False,
                unique=True,
                comment="LiveKit room name",
            ),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "ended_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "duration_seconds",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="Total duration of the voice session in seconds",
            ),
            sa.Column(
                "status",
                voice_session_status_enum,
                nullable=False,
                server_default="active",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )

        # Create indexes for voice_sessions
        op.create_index(
            "ix_voice_sessions_persona_owner_id",
            "voice_sessions",
            ["persona_owner_id"],
        )
        op.create_index(
            "ix_voice_sessions_persona_id",
            "voice_sessions",
            ["persona_id"],
        )
        op.create_index(
            "ix_voice_sessions_status",
            "voice_sessions",
            ["status"],
        )
        # Composite index for querying owner's usage in a time period
        op.create_index(
            "ix_voice_sessions_owner_started",
            "voice_sessions",
            ["persona_owner_id", "started_at"],
        )


def downgrade() -> None:
    """Remove voice usage limits and tracking tables."""
    # Drop indexes first
    op.drop_index("ix_voice_sessions_owner_started", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_status", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_persona_id", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_persona_owner_id", table_name="voice_sessions")

    # Drop table
    op.drop_table("voice_sessions")

    # Drop enum
    op.execute("DROP TYPE IF EXISTS voice_session_status_enum")

    # Remove columns from user_usage_cache
    op.drop_column("user_usage_cache", "voice_usage_reset_at")
    op.drop_column("user_usage_cache", "voice_seconds_used")

    # Remove column from tier_plans
    op.drop_column("tier_plans", "max_voice_minutes_per_month")
