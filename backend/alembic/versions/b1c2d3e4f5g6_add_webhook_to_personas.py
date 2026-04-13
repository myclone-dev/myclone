"""add_webhook_to_personas

Revision ID: b1c2d3e4f5g6
Revises: d3e148d9e454
Create Date: 2025-12-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5g6'
down_revision: Union[str, Sequence[str], None] = 'd3e148d9e454'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add webhook fields to personas table."""
    # Add webhook_enabled column
    op.add_column(
        'personas',
        sa.Column(
            'webhook_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment='Whether webhook integration is enabled for this persona'
        )
    )

    # Add webhook_url column
    op.add_column(
        'personas',
        sa.Column(
            'webhook_url',
            sa.String(length=500),
            nullable=True,
            comment='HTTPS webhook URL for receiving events'
        )
    )

    # Add webhook_events column (JSONB array of event types)
    op.add_column(
        'personas',
        sa.Column(
            'webhook_events',
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'[\"conversation.finished\"]'::jsonb"),
            comment='Array of event types to send to webhook'
        )
    )

    # Add webhook_secret column (for future HMAC signature verification)
    op.add_column(
        'personas',
        sa.Column(
            'webhook_secret',
            sa.String(length=255),
            nullable=True,
            comment='Optional secret for webhook signature verification'
        )
    )


def downgrade() -> None:
    """Remove webhook fields from personas table."""
    op.drop_column('personas', 'webhook_secret')
    op.drop_column('personas', 'webhook_events')
    op.drop_column('personas', 'webhook_url')
    op.drop_column('personas', 'webhook_enabled')
