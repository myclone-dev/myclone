"""add_calendar_to_personas

Revision ID: 8ae658a9d81f
Revises: 10ad9fd2fe04
Create Date: 2025-12-17 01:05:21.222297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8ae658a9d81f'
down_revision: Union[str, Sequence[str], None] = '10ad9fd2fe04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add calendar fields to personas table."""
    # Add calendar_enabled column
    op.add_column(
        'personas',
        sa.Column(
            'calendar_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment='Whether calendar integration is enabled for this persona'
        )
    )

    # Add calendar_url column
    op.add_column(
        'personas',
        sa.Column(
            'calendar_url',
            sa.String(length=500),
            nullable=True,
            comment='Calendly/Cal.com URL for booking calls with this persona'
        )
    )

    # Add calendar_display_name column
    op.add_column(
        'personas',
        sa.Column(
            'calendar_display_name',
            sa.String(length=100),
            nullable=True,
            comment='Display name for calendar link (e.g., "30-min intro call")'
        )
    )


def downgrade() -> None:
    """Remove calendar fields from personas table."""
    op.drop_column('personas', 'calendar_display_name')
    op.drop_column('personas', 'calendar_url')
    op.drop_column('personas', 'calendar_enabled')
