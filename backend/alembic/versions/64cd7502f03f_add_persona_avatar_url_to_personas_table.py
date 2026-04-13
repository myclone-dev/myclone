"""add persona_avatar_url to personas table

Revision ID: 64cd7502f03f
Revises: 6799ef3448b0
Create Date: 2026-01-27 00:24:00.022951

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64cd7502f03f'
down_revision: Union[str, Sequence[str], None] = 'c4f54eb94991'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add persona_avatar_url column to personas table."""
    op.add_column(
        'personas',
        sa.Column(
            'persona_avatar_url',
            sa.Text(),
            nullable=True,
            comment='Persona-specific avatar URL (S3). Overrides user avatar when set.'
        )
    )


def downgrade() -> None:
    """Remove persona_avatar_url column from personas table."""
    op.drop_column('personas', 'persona_avatar_url')
