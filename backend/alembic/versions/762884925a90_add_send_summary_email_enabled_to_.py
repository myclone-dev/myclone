"""Add send_summary_email_enabled to personas

Revision ID: 762884925a90
Revises: a710bf4e715c
Create Date: 2025-12-23 21:55:25.388882

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '762884925a90'
down_revision: Union[str, Sequence[str], None] = 'a710bf4e715c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add send_summary_email_enabled column to personas table."""
    op.add_column(
        'personas',
        sa.Column(
            'send_summary_email_enabled',
            sa.Boolean(),
            server_default='true',
            nullable=False,
            comment='Whether to send conversation summary emails to persona owner after conversations end'
        )
    )


def downgrade() -> None:
    """Remove send_summary_email_enabled column from personas table."""
    op.drop_column('personas', 'send_summary_email_enabled')
