"""add_conversational_workflow_support

Adds support for conversational workflow type with intelligent field extraction.

Changes:
- Adds output_template JSONB column to persona_workflows (for lead summaries)
- Adds extracted_fields JSONB column to workflow_sessions (for conversational field tracking)
- Adds GIN indexes for performance on JSONB columns

Note: All new columns are nullable for backward compatibility with existing simple/scored workflows.

Revision ID: 7ac6c5e769e2
Revises: c9a28ad8c760
Create Date: 2026-01-24 11:35:03.653938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7ac6c5e769e2'
down_revision: Union[str, Sequence[str], None] = 'c9a28ad8c760'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to support conversational workflows."""

    # ===== 1. Add output_template to persona_workflows =====
    # Used by conversational workflows for lead summary formatting
    op.add_column(
        "persona_workflows",
        sa.Column(
            "output_template",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Output template for conversational workflows (lead summary format, scoring rules, export destinations)",
        ),
    )

    # Add GIN index for efficient JSONB queries on output_template
    op.create_index(
        "idx_persona_workflows_output_template",
        "persona_workflows",
        ["output_template"],
        unique=False,
        postgresql_using="gin",
    )

    # ===== 2. Add extracted_fields to workflow_sessions =====
    # Used by conversational workflows to track field extraction with confidence scores
    op.add_column(
        "workflow_sessions",
        sa.Column(
            "extracted_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Extracted fields for conversational workflows (field_id -> {value, confidence, extraction_method})",
        ),
    )

    # Add GIN index for efficient JSONB queries on extracted_fields
    op.create_index(
        "idx_workflow_sessions_extracted_fields",
        "workflow_sessions",
        ["extracted_fields"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Downgrade schema - remove conversational workflow support."""

    # Remove indexes first (required before dropping columns)
    op.drop_index(
        "idx_workflow_sessions_extracted_fields",
        table_name="workflow_sessions",
        postgresql_using="gin",
    )
    op.drop_index(
        "idx_persona_workflows_output_template",
        table_name="persona_workflows",
        postgresql_using="gin",
    )

    # Remove columns
    op.drop_column("workflow_sessions", "extracted_fields")
    op.drop_column("persona_workflows", "output_template")
