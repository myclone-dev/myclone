"""add_workflow_templates_table

Revision ID: 757f6bc90da4
Revises: 7ac6c5e769e2
Create Date: 2026-01-25 04:34:50.442237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '757f6bc90da4'
down_revision: Union[str, Sequence[str], None] = '7ac6c5e769e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Create workflow_templates table."""

    # Create workflow_templates table
    op.create_table(
        'workflow_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),

        # Template identification
        sa.Column('template_key', sa.String(length=100), nullable=False, comment='Stable identifier for code references (e.g., cpa_lead_capture)'),
        sa.Column('template_name', sa.String(length=200), nullable=False, comment='Display name (e.g., CPA Lead Capture)'),
        sa.Column('template_category', sa.String(length=50), nullable=False, comment='Category for filtering (e.g., cpa, tax, insurance)'),

        # Access control (FK to tier_plans)
        sa.Column('minimum_plan_tier_id', sa.Integer(), nullable=False, server_default='0', comment='Minimum tier required (FK to tier_plans.id)'),

        # Template configuration
        sa.Column('workflow_type', sa.String(length=20), nullable=False, comment='Type of workflow (e.g., conversational)'),
        sa.Column('workflow_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Base field definitions, extraction strategy'),
        sa.Column('output_template', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Base scoring rules, follow-up questions, sections'),

        # Metadata (optional)
        sa.Column('description', sa.Text(), nullable=True, comment='Template description for UI'),
        sa.Column('workflow_objective', sa.Text(), nullable=True, comment='Suggested objective for guiding persona toward workflow (can be customized after enabling)'),
        sa.Column('preview_image_url', sa.Text(), nullable=True, comment='Screenshot/preview for template gallery'),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=True, comment='Tags for search/filtering'),

        # Versioning & status
        sa.Column('version', sa.Integer(), server_default='1', nullable=False, comment='Template version number'),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False, comment='Whether template is available in library'),

        # Audit & ownership
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True, comment='User who created template (NULL = system/admin)'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('published_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='When template was published'),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_key'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['minimum_plan_tier_id'], ['tier_plans.id'], ondelete='RESTRICT'),
    )

    # Create indexes
    op.create_index('idx_workflow_templates_key', 'workflow_templates', ['template_key'])
    op.create_index('idx_workflow_templates_category', 'workflow_templates', ['template_category'])
    op.create_index('idx_workflow_templates_active', 'workflow_templates', ['is_active'])
    op.create_index('idx_workflow_templates_tier_id', 'workflow_templates', ['minimum_plan_tier_id'])
    op.create_index('idx_workflow_templates_config', 'workflow_templates', ['workflow_config'], postgresql_using='gin')


def downgrade() -> None:
    """Downgrade schema - Drop workflow_templates table."""

    # Drop indexes first
    op.drop_index('idx_workflow_templates_config', table_name='workflow_templates')
    op.drop_index('idx_workflow_templates_tier_id', table_name='workflow_templates')
    op.drop_index('idx_workflow_templates_active', table_name='workflow_templates')
    op.drop_index('idx_workflow_templates_category', table_name='workflow_templates')
    op.drop_index('idx_workflow_templates_key', table_name='workflow_templates')

    # Drop table
    op.drop_table('workflow_templates')
