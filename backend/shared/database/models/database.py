import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, AsyncGenerator, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .conversation_attachment import ConversationAttachment
    from .persona_access import PersonaVisitor
    from .scraping import PersonaDataSource
    from .stripe import PersonaAccessPurchase, PersonaPricing
    from .text_session import TextSession
    from .user import User
    from .voice_session import VoiceSession
    from .workflow import PersonaWorkflow

# Import shared Base
from shared.database.base import Base


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User who owns this persona - enables multiple personas per user",
    )
    persona_name: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="default"
    )  # Persona name (unique per user via composite constraint, default="default")
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Professional role/title
    expertise: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Areas of expertise
    description: Mapped[Optional[str]] = mapped_column(Text)
    voice_id: Mapped[Optional[str]] = mapped_column(String(255))  # ElevenLabs voice ID for persona
    voice_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default="true",
        nullable=False,
        comment="Whether voice chat is enabled for this persona",
    )
    greeting_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Custom greeting for voice chat
    language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        server_default="auto",
        comment="Language code for persona responses (auto, en, hi, es, fr, zh, de, ar, it). NULL=auto, default='auto'",
    )  # Language preference for TTS and responses

    # Persona-specific avatar (overrides user avatar)
    persona_avatar_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Persona-specific avatar URL (S3). Overrides user avatar when set.",
    )

    # Calendar Integration
    calendar_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
        comment="Whether calendar integration is enabled for this persona",
    )
    calendar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Calendly/Cal.com URL for booking calls with this persona",
    )
    calendar_display_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment='Display name for calendar link (e.g., "30-min intro call")',
    )

    # Access Control
    # Private personas require email verification + allowlist
    is_private: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    # When access control was enabled
    access_control_enabled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Default Lead Capture Settings
    # Enable conversational lead capture (agent asks for name/email/phone naturally)
    default_lead_capture_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
        comment="Whether agent captures visitor contact info via conversation",
    )

    # Content Mode (dogfooding - off by default)
    content_mode_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
        comment="Whether content creation mode is enabled for this persona",
    )

    # Email Capture Settings (popup - legacy, to be deprecated)
    # Enable email capture after N messages
    email_capture_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
        comment="Whether to prompt visitors for email",
    )
    email_capture_message_threshold: Mapped[int] = mapped_column(
        Integer,
        server_default="5",
        nullable=False,
        comment="Number of messages before prompting for email (default: 5)",
    )
    email_capture_require_fullname: Mapped[bool] = mapped_column(
        Boolean,
        server_default="true",
        nullable=False,
        comment="Whether full name is required when capturing email",
    )
    email_capture_require_phone: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
        comment="Whether phone number is required when capturing email",
    )

    # Session Time Limit Settings
    session_time_limit_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
        comment="Whether session time limits are enforced for visitors",
    )
    session_time_limit_minutes: Mapped[float] = mapped_column(
        Float,
        server_default="30.0",
        nullable=False,
        comment="Maximum session duration in minutes (default: 30, supports fractions like 2.5 for 2m 30s)",
    )
    session_time_limit_warning_minutes: Mapped[float] = mapped_column(
        Float,
        server_default="2.0",
        nullable=False,
        comment="Minutes before limit to show warning (supports fractions like 0.5 for 30s)",
    )

    # Conversation Summary Email Settings
    send_summary_email_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default="true",
        nullable=False,
        comment="Whether to send conversation summary emails to persona owner after conversations end",
    )
    # Webhook Integration
    webhook_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
        comment="Whether webhook integration is enabled for this persona",
    )
    webhook_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="HTTPS webhook URL for receiving events",
    )
    webhook_events: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        server_default='["conversation.finished"]',
        comment="Array of event types to send to webhook",
    )
    webhook_secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional secret for webhook signature verification",
    )

    # Soft Delete
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    suggested_questions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="Persona-specific suggested starter questions for chat UI.\n"
        '        Format: {"questions": ["Q1?", "Q2?"], "generated_at": "ISO timestamp"}',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="personas")  # NEW
    patterns: Mapped[List["Pattern"]] = relationship(
        back_populates="persona", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="persona", cascade="all, delete-orphan"
    )
    user_sessions: Mapped[List["UserSession"]] = relationship(
        back_populates="persona", cascade="all, delete-orphan"
    )
    data_sources: Mapped[List["PersonaDataSource"]] = relationship(  # NEW
        back_populates="persona", cascade="all, delete-orphan"
    )
    persona_prompts: Mapped[List["PersonaPrompt"]] = relationship(
        back_populates="persona", cascade="all, delete-orphan"
    )
    prompt_templates: Mapped[List["PromptTemplate"]] = relationship(
        back_populates="persona", cascade="all, delete-orphan"
    )
    persona_visitors: Mapped[List["PersonaVisitor"]] = relationship(
        back_populates="persona", cascade="all, delete-orphan"
    )
    # Stripe relationships
    persona_pricing: Mapped[Optional["PersonaPricing"]] = relationship(
        back_populates="persona", uselist=False, cascade="all, delete-orphan"
    )
    persona_purchases: Mapped[List["PersonaAccessPurchase"]] = relationship(
        back_populates="persona"
    )
    # Workflow relationships
    workflows: Mapped[List["PersonaWorkflow"]] = relationship(
        back_populates="persona", cascade="all, delete-orphan"
    )
    # Note: custom_domains are USER-LEVEL, not persona-level
    # See User model for custom_domains relationship
    # Session tracking
    voice_sessions: Mapped[List["VoiceSession"]] = relationship(
        back_populates="persona", cascade="all, delete-orphan"
    )
    text_sessions: Mapped[List["TextSession"]] = relationship(
        back_populates="persona",
        cascade="all, delete-orphan",
        foreign_keys="[TextSession.persona_id]",
    )

    __table_args__ = (
        Index(
            "uq_personas_user_persona_name_active",
            "user_id",
            "persona_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("idx_personas_user_id", "user_id"),
        Index("idx_personas_is_active", "is_active"),
        Index(
            "idx_personas_suggested_questions",
            "suggested_questions",
            postgresql_using="gin",
        ),
    )


class Pattern(Base):
    __tablename__ = "patterns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("personas.id"))
    pattern_type: Mapped[str] = mapped_column(String(100))
    pattern_data: Mapped[dict] = mapped_column(JSONB)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    persona: Mapped["Persona"] = relationship(back_populates="patterns")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conversations_voice_session", "persona_id", "session_id", "conversation_type"),
        Index(
            "idx_conversations_summary_generated",
            "id",
            "summary_generated_at",
            postgresql_where=text("summary_generated_at IS NOT NULL"),
        ),
        Index("ix_conversations_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("personas.id"))
    session_id: Mapped[Optional[str]] = mapped_column(String(255))
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key to users table - NULL for anonymous conversations, UUID for authenticated users",
    )
    user_email: Mapped[Optional[str]] = mapped_column(
        String(255)
    )  # Added for user session association
    user_fullname: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="User's full name (captured during email collection)",
    )
    user_phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="User's phone number (optional during email collection)",
    )
    conversation_type: Mapped[str] = mapped_column(String(50), default="text")  # 'text' or 'voice'
    messages: Mapped[list] = mapped_column(JSONB, default=list)
    conversation_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # AI Summary Cache (generated on-demand, cached for performance)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    summary_generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    persona: Mapped["Persona"] = relationship(back_populates="conversations")
    attachments: Mapped[List["ConversationAttachment"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class PersonaPrompt(Base):
    __tablename__ = "persona_prompts"
    __table_args__ = (
        Index(
            "uq_persona_prompts_active",
            "persona_id",
            "is_active",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    introduction: Mapped[str] = mapped_column(Text)
    thinking_style: Mapped[Optional[str]] = mapped_column(Text)
    area_of_expertise: Mapped[Optional[str]] = mapped_column(Text)
    chat_objective: Mapped[Optional[str]] = mapped_column(Text)
    objective_response: Mapped[Optional[str]] = mapped_column(Text)
    example_responses: Mapped[Optional[str]] = mapped_column(Text)
    target_audience: Mapped[Optional[str]] = mapped_column(Text)
    prompt_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="FK to prompt_templates - tracks which template was used to generate this prompt",
    )
    example_prompt: Mapped[Optional[str]] = mapped_column(Text)
    is_dynamic: Mapped[bool] = mapped_column(Boolean, default=False)
    # Newly added columns
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    response_structure: Mapped[Optional[str]] = mapped_column(Text)
    conversation_flow: Mapped[Optional[str]] = mapped_column(Text)
    strict_guideline: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(back_populates="persona_prompts")
    prompt_template_rel: Mapped[Optional["PromptTemplate"]] = relationship()


class PersonaPromptHistory(Base):
    """
    History table for PersonaPrompt versioning and auditing.
    Stores previous versions when updates/deletes occur.
    Current active version remains only in persona_prompts table.
    """

    __tablename__ = "persona_prompts_history"

    # Replica of all PersonaPrompt columns
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persona_prompts.id", ondelete="SET NULL"), nullable=True
    )  # ID from original persona_prompts table
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    introduction: Mapped[str] = mapped_column(Text, nullable=False)
    thinking_style: Mapped[Optional[str]] = mapped_column(Text)
    area_of_expertise: Mapped[Optional[str]] = mapped_column(Text)
    chat_objective: Mapped[Optional[str]] = mapped_column(Text)
    objective_response: Mapped[Optional[str]] = mapped_column(Text)
    example_responses: Mapped[Optional[str]] = mapped_column(Text)
    target_audience: Mapped[Optional[str]] = mapped_column(Text)
    prompt_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_templates.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK to prompt_templates - tracks which template was used",
    )
    example_prompt: Mapped[Optional[str]] = mapped_column(Text)
    is_dynamic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    response_structure: Mapped[Optional[str]] = mapped_column(Text)
    conversation_flow: Mapped[Optional[str]] = mapped_column(Text)
    strict_guideline: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )  # Timestamp when this history entry was created (i.e., when the version was archived)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # History/versioning specific columns
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # 'UPDATE', 'DELETE', 'RESTORE'

    # Indexes for performance
    __table_args__ = (Index("ix_persona_prompts_history_operation", "operation"),)

    # Relationships
    original_persona_prompt: Mapped[Optional["PersonaPrompt"]] = relationship()
    persona: Mapped["Persona"] = relationship()


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint(
            "type",
            "expertise",
            "persona_id",
            "platform",
            "is_active",
            name="uq_prompt_template_unique_active",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template: Mapped[str] = mapped_column(Text)
    example: Mapped[Optional[str]] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(20))  # Should be one of: "basic", "advance", "test"
    expertise: Mapped[Optional[str]] = mapped_column(Text)
    persona_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=True
    )
    platform: Mapped[str] = mapped_column(
        String(20)
    )  # Should be one of: "openai", "custom", "local", "gemini", "qwen", "claude"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    thinking_style: Mapped[Optional[str]] = mapped_column(Text)
    chat_objective: Mapped[Optional[str]] = mapped_column(Text)
    objective_response: Mapped[Optional[str]] = mapped_column(Text)
    response_structure: Mapped[Optional[str]] = mapped_column(Text)
    conversation_flow: Mapped[Optional[str]] = mapped_column(Text)
    strict_guideline: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    persona: Mapped[Optional["Persona"]] = relationship(back_populates="prompt_templates")


class Waitlist(Base):
    __tablename__ = "waitlist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


from shared.database.config import get_database_url

# Import UserSession after other models are defined to avoid circular imports
from shared.database.models.user_session import UserSession

engine = create_async_engine(get_database_url(), echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """
    Initialize database - creates required PostgreSQL extensions only.

    IMPORTANT: Table creation is handled by Alembic migrations, NOT here.
    Run migrations separately: make migrate (or alembic upgrade head)

    This ensures:
    - Proper migration history tracking
    - Rollback capability
    - Consistent schema across environments
    - Team collaboration on schema changes
    """
    async with engine.begin() as conn:
        # Create required PostgreSQL extensions
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # NOTE: Base.metadata.create_all() is intentionally NOT called here
        # All schema changes MUST go through Alembic migrations
        # To apply migrations: docker-compose exec api alembic upgrade head


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
