"""
Database models for the workflow system.

Supports three workflow types:
- simple: Just questions (collect info, no scoring)
- scored: Questions with scoring and result categories
- conversational: LLM-based field extraction with lead scoring

Question types supported (for simple/scored):
- text_input: Single line text
- text_area: Multi-line text
- number_input: Numeric value
- multiple_choice: Options with optional scoring
- yes_no: Boolean

Template System (for conversational workflows):
- WorkflowTemplate: Master template library (admin-managed)
- PersonaWorkflow: Workflow instances (can be created from templates)
- Copy-on-enable pattern: Templates are copied, users can customize

Created: 2025-12-08
Updated: 2026-01-25 (added template system)
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .database import Conversation, Persona
    from .user import User

from shared.database.base import Base


class WorkflowTemplate(Base):
    """
    Master template library for conversational workflows.

    Templates are admin-managed, enterprise-only workflow configurations
    that users can enable for their personas and customize.

    Architecture: Copy-on-Enable
    - User enables template → workflow_config COPIED to persona_workflows
    - User can customize after enabling → is_template_customized = True
    - Template updates can be synced if not customized

    Example:
    - "CPA Lead Capture" template (base, generic fields)
    - AMI CPA enables → customizes for individual tax + FBAR
    - Lion Star Tax enables → customizes for business tax + entity formation
    """

    __tablename__ = "workflow_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    # Template identification
    template_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        comment="Stable identifier for code references (e.g., cpa_lead_capture)",
    )

    template_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Display name (e.g., CPA Lead Capture)",
    )

    template_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Category for filtering (e.g., cpa, tax, insurance)",
    )

    # Access control (FK to tier_plans)
    minimum_plan_tier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tier_plans.id", ondelete="RESTRICT"),
        server_default="0",
        nullable=False,
        comment="Minimum tier required (FK to tier_plans.id)",
    )

    # Template configuration (same structure as persona_workflows)
    workflow_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Type of workflow (e.g., conversational)",
    )

    workflow_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Base field definitions, extraction strategy",
    )

    output_template: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Base scoring rules, follow-up questions, sections",
    )

    # Metadata (optional)
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Template description for UI",
    )

    workflow_objective: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Suggested objective for guiding persona toward workflow (can be customized after enabling)",
    )

    preview_image_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Screenshot/preview for template gallery",
    )

    tags: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text),
        nullable=True,
        comment="Tags for search/filtering",
    )

    # Versioning & status
    version: Mapped[int] = mapped_column(
        Integer,
        server_default="1",
        nullable=False,
        comment="Template version number",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default="true",
        nullable=False,
        comment="Whether template is available in library",
    )

    # Audit & ownership
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created template (NULL = system/admin)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When template was published",
    )

    # Relationships
    creator: Mapped[Optional["User"]] = relationship()
    workflows: Mapped[list["PersonaWorkflow"]] = relationship(back_populates="template")

    __table_args__ = (
        Index("idx_workflow_templates_key", "template_key"),
        Index("idx_workflow_templates_category", "template_category"),
        Index("idx_workflow_templates_active", "is_active"),
        Index("idx_workflow_templates_tier_id", "minimum_plan_tier_id"),
        Index("idx_workflow_templates_config", "workflow_config", postgresql_using="gin"),
    )


class PersonaWorkflow(Base):
    """
    Workflows define structured conversation flows for personas.

    Each workflow contains:
    - steps: Array of questions with type, text, options, validation
    - result_config: Optional scoring and result categories (for scored workflows)

    Workflows are versioned - updates create new versions with old ones deactivated.
    """

    __tablename__ = "persona_workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
        comment="Persona this workflow belongs to",
    )

    # Workflow type: 'simple' (just questions) or 'scored' (questions + scoring)
    workflow_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Workflow type: 'simple' or 'scored'",
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Workflow title (e.g., 'Business Growth Assessment')",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Internal description (not shown to users)",
    )

    opening_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Message shown before first question (optional)",
    )

    workflow_objective: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="LLM-generated objective for guiding user toward workflow (overrides chat_objective)",
    )

    # Flexible JSONB configuration
    # Structure: {
    #   "steps": [
    #     {
    #       "step_id": "q1",
    #       "step_type": "text_input",
    #       "question_text": "What's your company name?",
    #       "required": true,
    #       "validation": {"min_length": 2, "max_length": 100}
    #     },
    #     {
    #       "step_id": "q2",
    #       "step_type": "multiple_choice",
    #       "question_text": "What stage are you at?",
    #       "required": true,
    #       "options": [
    #         {"label": "A", "text": "Pre-seed", "value": "pre_seed", "score": 1},
    #         {"label": "B", "text": "Seed", "value": "seed", "score": 2}
    #       ]
    #     }
    #   ]
    # }
    workflow_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Workflow configuration (steps, questions, options, validation)",
    )

    # Only for scored workflows
    # Structure: {
    #   "scoring_type": "sum",
    #   "categories": [
    #     {
    #       "name": "Not Ready",
    #       "min_score": 14,
    #       "max_score": 26,
    #       "message": "Both you and your business need strengthening..."
    #     }
    #   ]
    # }
    result_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Result configuration (scoring type, categories, messages)",
    )

    # Workflow lifecycle
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default="true",
        nullable=False,
        comment="Whether workflow is active (only one version active at a time)",
    )

    version: Mapped[int] = mapped_column(
        Integer,
        server_default="1",
        nullable=False,
        comment="Workflow version number (increments on updates)",
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When workflow was published (null = draft)",
    )

    # Trigger settings (optional, can be added later)
    # trigger_type: 'manual' (user says "take quiz") or 'auto' (after N messages)
    # trigger_config: {"trigger_phrase": "quiz", "auto_start_after_messages": 5}
    trigger_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Trigger settings (when to start workflow)",
    )

    # Metadata (extensible) - using 'extra_metadata' to avoid SQLAlchemy reserved name
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata (tags, notes, etc.)",
    )

    # Output template (for conversational workflows)
    output_template: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Output template for conversational workflows (lead summary format, scoring rules, export destinations)",
    )

    # Template tracking (added 2026-01-25)
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_templates.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to template this workflow was created from",
    )

    is_template_customized: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
        comment="True if user has modified the template config",
    )

    template_version: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Version of template when workflow was created/last synced",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(back_populates="workflows")
    template: Mapped[Optional["WorkflowTemplate"]] = relationship(back_populates="workflows")
    sessions: Mapped[list["WorkflowSession"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_persona_workflows_persona", "persona_id"),
        Index("idx_persona_workflows_active", "is_active"),
        Index("idx_persona_workflows_type", "workflow_type"),
        Index("idx_persona_workflows_template", "template_id"),  # Added 2026-01-25
        # GIN index for JSONB queries (e.g., searching workflow config)
        Index(
            "idx_persona_workflows_config",
            "workflow_config",
            postgresql_using="gin",
        ),
        Index(
            "idx_persona_workflows_output_template",
            "output_template",
            postgresql_using="gin",
        ),
    )


class WorkflowSession(Base):
    """
    Tracks individual workflow executions (user taking assessment).

    Each session stores:
    - Progress tracking (current step, percentage)
    - Collected answers (all responses in JSONB)
    - Result data (final score, category for scored workflows)
    """

    __tablename__ = "workflow_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persona_workflows.id", ondelete="CASCADE"),
        nullable=False,
        comment="Workflow being executed",
    )

    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
        comment="Persona conducting the workflow",
    )

    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated conversation (if workflow started in chat)",
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User taking the workflow (if authenticated)",
    )

    # Session token for linking to conversations
    session_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Session token for linking to conversations (matches conversations.session_id)",
    )

    # Session status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="in_progress",
        comment="Session status: 'in_progress', 'completed', 'abandoned'",
    )

    # Progress tracking
    current_step_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Current question step_id (null when completed)",
    )

    progress_percentage: Mapped[int] = mapped_column(
        Integer,
        server_default="0",
        nullable=False,
        comment="Progress percentage (0-100)",
    )

    # Collected data from user
    # Structure: {
    #   "q1": {
    #     "question": "What's your company name?",
    #     "answer": "Acme Corp",
    #     "answered_at": "2025-12-08T10:05:00Z"
    #   },
    #   "q2": {
    #     "question": "What stage are you at?",
    #     "answer": "seed",
    #     "raw_answer": "We're at seed stage",
    #     "score": 2,
    #     "answered_at": "2025-12-08T10:06:00Z"
    #   }
    # }
    collected_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="'{}'::jsonb",
        comment="All user responses (questions, answers, scores)",
    )

    # Results (for scored workflows)
    # Structure: {
    #   "total_score": 38,
    #   "max_possible_score": 56,
    #   "percentage": 67.8,
    #   "category": "Emerging",
    #   "category_message": "You've got traction but scaling is fragile..."
    # }
    result_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Final results (score, category, message for scored workflows)",
    )

    # Extracted fields (for conversational workflows)
    extracted_fields: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Extracted fields for conversational workflows (field_id -> {value, confidence, extraction_method})",
    )

    # Session metadata (extensible)
    session_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional session metadata (user agent, IP, etc.)",
    )

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="When workflow session started",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When workflow was completed (null = not completed)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    workflow: Mapped["PersonaWorkflow"] = relationship(back_populates="sessions")
    persona: Mapped["Persona"] = relationship()
    conversation: Mapped[Optional["Conversation"]] = relationship()
    user: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        Index("idx_workflow_sessions_workflow", "workflow_id"),
        Index("idx_workflow_sessions_persona", "persona_id"),
        Index("idx_workflow_sessions_status", "status"),
        Index("idx_workflow_sessions_user", "user_id"),
        Index("idx_workflow_sessions_conversation", "conversation_id"),
        # Index for analytics queries (completed sessions only)
        Index(
            "idx_workflow_sessions_completed",
            "workflow_id",
            "completed_at",
            postgresql_where=text("status = 'completed'"),
        ),
        # GIN index for JSONB queries (e.g., searching collected answers)
        Index(
            "idx_workflow_sessions_collected_data",
            "collected_data",
            postgresql_using="gin",
        ),
        Index(
            "idx_workflow_sessions_result_data",
            "result_data",
            postgresql_using="gin",
        ),
        Index(
            "idx_workflow_sessions_extracted_fields",
            "extracted_fields",
            postgresql_using="gin",
        ),
    )
