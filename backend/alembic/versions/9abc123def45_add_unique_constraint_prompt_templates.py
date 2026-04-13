"""Add composite unique constraint to prompt_templates

Revision ID: 9abc123def45
Revises: 8e1a2b3c4d5e
Create Date: 2025-09-26 00:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9abc123def45'
down_revision = '8e1a2b3c4d5e'
branch_labels = None
depends_on = None

CONSTRAINT_NAME = 'uq_prompt_template_unique_active'


def upgrade():
    # 1. Remove duplicate rows that would violate the new constraint, keeping the most recently updated (or highest id as tie-breaker)
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY type, expertise, persona_username, platform, is_active
                           ORDER BY updated_at DESC NULLS LAST, id DESC
                       ) AS rn
                FROM prompt_templates
            )
            DELETE FROM prompt_templates pt
            USING ranked r
            WHERE pt.id = r.id AND r.rn > 1;
            """
        )
    )

    # 2. Add the composite unique constraint
    op.create_unique_constraint(
        CONSTRAINT_NAME,
        'prompt_templates',
        ['type', 'expertise', 'persona_username', 'platform', 'is_active']
    )


def downgrade():
    # Drop the unique constraint
    op.drop_constraint(CONSTRAINT_NAME, 'prompt_templates', type_='unique')

