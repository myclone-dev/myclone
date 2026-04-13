"""add_language_column_to_personas

Revision ID: 48accb79d506
Revises: c158a002485e
Create Date: 2026-01-15 16:07:39.309406

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '48accb79d506'
down_revision: Union[str, Sequence[str], None] = 'c158a002485e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add language column to personas table.

    Supported languages:
    - auto: No language restriction (default)
    - en: English
    - hi: Hindi
    - es: Spanish
    - fr: French
    - zh: Chinese
    - de: German
    - ar: Arabic
    - it: Italian

    NULL values are treated as 'auto' (no restriction).
    """
    op.add_column(
        'personas',
        sa.Column(
            'language',
            sa.String(10),
            nullable=True,
            comment='Language code for persona responses (auto, en, hi, es, fr, zh, de, ar, it). NULL=auto'
        )
    )


def downgrade() -> None:
    """Remove language column from personas table."""
    op.drop_column('personas', 'language')

