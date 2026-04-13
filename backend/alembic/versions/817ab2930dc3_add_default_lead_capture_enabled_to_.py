"""add_default_lead_capture_enabled_to_personas

Revision ID: 817ab2930dc3
Revises: 61487e32c389
Create Date: 2026-02-13 20:59:39.533565

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "817ab2930dc3"
down_revision: Union[str, Sequence[str], None] = "61487e32c389"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add default_lead_capture_enabled flag to personas."""
    op.add_column(
        "personas",
        sa.Column(
            "default_lead_capture_enabled",
            sa.Boolean(),
            server_default="false",
            nullable=False,
            comment="Whether agent captures visitor contact info via conversation",
        ),
    )


def downgrade() -> None:
    """Remove default_lead_capture_enabled flag from personas."""
    op.drop_column("personas", "default_lead_capture_enabled")
