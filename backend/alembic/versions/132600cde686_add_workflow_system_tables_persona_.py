"""add workflow system tables persona_workflows and workflow_sessions

Revision ID: 132600cde686
Revises: ca5c192f3e3e
Create Date: 2025-12-08 20:34:59.038830

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "132600cde686"
down_revision: Union[str, Sequence[str], None] = "ca5c192f3e3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "persona_workflows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "persona_id", sa.UUID(), nullable=False, comment="Persona this workflow belongs to"
        ),
        sa.Column(
            "workflow_type",
            sa.String(length=20),
            nullable=False,
            comment="Workflow type: 'simple' or 'scored'",
        ),
        sa.Column(
            "title",
            sa.String(length=500),
            nullable=False,
            comment="Workflow title (e.g., 'Business Growth Assessment')",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Internal description (not shown to users)",
        ),
        sa.Column(
            "opening_message",
            sa.Text(),
            nullable=True,
            comment="Message shown before first question (optional)",
        ),
        sa.Column(
            "workflow_objective",
            sa.Text(),
            nullable=True,
            comment="LLM-generated objective for guiding user toward workflow (overrides chat_objective)",
        ),
        sa.Column(
            "workflow_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Workflow configuration (steps, questions, options, validation)",
        ),
        sa.Column(
            "result_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Result configuration (scoring type, categories, messages)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
            comment="Whether workflow is active (only one version active at a time)",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="Workflow version number (increments on updates)",
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When workflow was published (null = draft)",
        ),
        sa.Column(
            "trigger_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Trigger settings (when to start workflow)",
        ),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Additional metadata (tags, notes, etc.)",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_persona_workflows_active", "persona_workflows", ["is_active"], unique=False
    )
    op.create_index(
        "idx_persona_workflows_config",
        "persona_workflows",
        ["workflow_config"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "idx_persona_workflows_persona", "persona_workflows", ["persona_id"], unique=False
    )
    op.create_index(
        "idx_persona_workflows_type", "persona_workflows", ["workflow_type"], unique=False
    )
    op.create_table(
        "workflow_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False, comment="Workflow being executed"),
        sa.Column(
            "persona_id", sa.UUID(), nullable=False, comment="Persona conducting the workflow"
        ),
        sa.Column(
            "conversation_id",
            sa.UUID(),
            nullable=True,
            comment="Associated conversation (if workflow started in chat)",
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=True,
            comment="User taking the workflow (if authenticated)",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="in_progress",
            nullable=False,
            comment="Session status: 'in_progress', 'completed', 'abandoned'",
        ),
        sa.Column(
            "current_step_id",
            sa.String(length=100),
            nullable=True,
            comment="Current question step_id (null when completed)",
        ),
        sa.Column(
            "progress_percentage",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Progress percentage (0-100)",
        ),
        sa.Column(
            "collected_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="All user responses (questions, answers, scores)",
        ),
        sa.Column(
            "result_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Final results (score, category, message for scored workflows)",
        ),
        sa.Column(
            "session_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Additional session metadata (user agent, IP, etc.)",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When workflow session started",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When workflow was completed (null = not completed)",
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["persona_workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_workflow_sessions_collected_data",
        "workflow_sessions",
        ["collected_data"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "idx_workflow_sessions_completed",
        "workflow_sessions",
        ["workflow_id", "completed_at"],
        unique=False,
        postgresql_where=sa.text("status = 'completed'"),
    )
    op.create_index(
        "idx_workflow_sessions_conversation", "workflow_sessions", ["conversation_id"], unique=False
    )
    op.create_index(
        "idx_workflow_sessions_persona", "workflow_sessions", ["persona_id"], unique=False
    )
    op.create_index(
        "idx_workflow_sessions_result_data",
        "workflow_sessions",
        ["result_data"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index("idx_workflow_sessions_status", "workflow_sessions", ["status"], unique=False)
    op.create_index("idx_workflow_sessions_user", "workflow_sessions", ["user_id"], unique=False)
    op.create_index(
        "idx_workflow_sessions_workflow", "workflow_sessions", ["workflow_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("idx_workflow_sessions_workflow", table_name="workflow_sessions")
    op.drop_index("idx_workflow_sessions_user", table_name="workflow_sessions")
    op.drop_index("idx_workflow_sessions_status", table_name="workflow_sessions")
    op.drop_index(
        "idx_workflow_sessions_result_data", table_name="workflow_sessions", postgresql_using="gin"
    )
    op.drop_index("idx_workflow_sessions_persona", table_name="workflow_sessions")
    op.drop_index("idx_workflow_sessions_conversation", table_name="workflow_sessions")
    op.drop_index(
        "idx_workflow_sessions_completed",
        table_name="workflow_sessions",
        postgresql_where=sa.text("status = 'completed'"),
    )
    op.drop_index(
        "idx_workflow_sessions_collected_data",
        table_name="workflow_sessions",
        postgresql_using="gin",
    )
    op.drop_table("workflow_sessions")
    op.drop_index("idx_persona_workflows_type", table_name="persona_workflows")
    op.drop_index("idx_persona_workflows_persona", table_name="persona_workflows")
    op.drop_index(
        "idx_persona_workflows_config", table_name="persona_workflows", postgresql_using="gin"
    )
    op.drop_index("idx_persona_workflows_active", table_name="persona_workflows")
    op.drop_table("persona_workflows")
    # ### end Alembic commands ###
