"""add_template_columns_to_persona_workflows

Revision ID: 346f0e7a1fad
Revises: 757f6bc90da4
Create Date: 2026-01-25 04:35:31.738117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '346f0e7a1fad'
down_revision: Union[str, Sequence[str], None] = '757f6bc90da4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add template tracking columns to persona_workflows."""

    # Add template_id column (foreign key to workflow_templates)
    op.add_column(
        'persona_workflows',
        sa.Column(
            'template_id',
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment='Reference to template this workflow was created from'
        )
    )

    # Add is_template_customized flag
    op.add_column(
        'persona_workflows',
        sa.Column(
            'is_template_customized',
            sa.Boolean(),
            server_default='false',
            nullable=False,
            comment='True if user has modified the template config'
        )
    )

    # Add template_version column (snapshot of template version when enabled)
    op.add_column(
        'persona_workflows',
        sa.Column(
            'template_version',
            sa.Integer(),
            nullable=True,
            comment='Version of template when workflow was created/last synced'
        )
    )

    # Create foreign key constraint
    op.create_foreign_key(
        'fk_persona_workflows_template_id',
        'persona_workflows',
        'workflow_templates',
        ['template_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Create index on template_id for faster lookups
    op.create_index(
        'idx_persona_workflows_template',
        'persona_workflows',
        ['template_id']
    )


def downgrade() -> None:
    """Downgrade schema - Remove template tracking columns from persona_workflows."""

    # Drop index first
    op.drop_index('idx_persona_workflows_template', table_name='persona_workflows')

    # Drop foreign key constraint
    op.drop_constraint('fk_persona_workflows_template_id', 'persona_workflows', type_='foreignkey')

    # Drop columns
    op.drop_column('persona_workflows', 'template_version')
    op.drop_column('persona_workflows', 'is_template_customized')
    op.drop_column('persona_workflows', 'template_id')
