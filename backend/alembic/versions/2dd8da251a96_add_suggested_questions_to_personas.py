"""add_suggested_questions_to_personas

Revision ID: 2dd8da251a96
Revises: 006b0f34361e
Create Date: 2025-10-31 16:58:39

Add suggested_questions JSONB column to personas table for storing
persona-specific suggested starter questions for chat UI.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2dd8da251a96'
down_revision: Union[str, Sequence[str], None] = '006b0f34361e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add suggested_questions JSONB column to personas table."""
    # Add suggested_questions column to personas table
    op.add_column(
        'personas',
        sa.Column('suggested_questions', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # Add GIN index for fast JSONB queries (optional but recommended)
    op.create_index(
        'idx_personas_suggested_questions',
        'personas',
        ['suggested_questions'],
        unique=False,
        postgresql_using='gin'
    )

    # Add comment to explain the column purpose
    op.execute("""
        COMMENT ON COLUMN personas.suggested_questions IS
        'Persona-specific suggested starter questions for chat UI.
        Format: {"questions": ["Q1?", "Q2?"], "generated_at": "ISO timestamp"}'
    """)


def downgrade() -> None:
    """Remove suggested_questions column from personas table."""
    # Drop index first
    op.drop_index('idx_personas_suggested_questions', table_name='personas')

    # Drop column
    op.drop_column('personas', 'suggested_questions')
