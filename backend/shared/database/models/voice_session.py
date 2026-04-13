"""
Voice session model for tracking voice chat usage.

Voice usage is charged to the PERSONA OWNER, not the caller.
When anyone calls a persona, the owner's monthly quota is consumed.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from .database import Base

if TYPE_CHECKING:
    from .persona import Persona
    from .user import User


class VoiceSessionStatus(str, enum.Enum):
    """Status of a voice session"""

    ACTIVE = "active"  # Session is ongoing
    COMPLETED = "completed"  # Session ended normally
    LIMIT_EXCEEDED = "limit_exceeded"  # Session ended due to owner's limit
    DISCONNECTED = "disconnected"  # Session ended due to network issues
    TIMEOUT = "timeout"  # Session ended due to inactivity (stale cleanup)


class RecordingStatus(str, enum.Enum):
    """Status of a voice session recording"""

    DISABLED = "disabled"  # Recording not enabled
    STARTING = "starting"  # Recording initiation in progress
    ACTIVE = "active"  # Recording in progress
    STOPPING = "stopping"  # Recording stop in progress
    COMPLETED = "completed"  # Recording successfully saved to S3
    FAILED = "failed"  # Recording failed
    STOPPED = "stopped"  # Recording manually stopped


class VoiceSession(Base):
    """
    Tracks individual voice chat sessions for usage metering.

    Usage is charged to the PERSONA OWNER:
    - When a visitor calls any persona, the owner's quota is consumed
    - Owner's tier determines their monthly limit
    - All personas owned by a user share the same quota

    This table enables:
    - Real-time tracking of active sessions
    - Historical usage analytics
    - Per-persona usage breakdown for the owner's dashboard
    """

    __tablename__ = "voice_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
    )
    persona_owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Persona owner whose quota is consumed",
    )
    caller_session_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Caller session token (for analytics only)",
    )
    room_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="LiveKit room name",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Total duration of the voice session in seconds",
    )
    status: Mapped[VoiceSessionStatus] = mapped_column(
        SQLEnum(
            VoiceSessionStatus,
            name="voice_session_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        server_default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # Recording fields (LiveKit egress integration)
    egress_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="LiveKit egress ID for tracking recording",
    )
    recording_s3_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="S3 path to recording file (e.g., recordings/{persona_id}/{session_id}.mp4)",
    )
    recording_status: Mapped[RecordingStatus] = mapped_column(
        SQLEnum(
            RecordingStatus,
            name="recording_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        server_default="disabled",
        comment="Status of the recording",
    )

    # Relationships
    persona: Mapped["Persona"] = relationship("Persona", back_populates="voice_sessions")
    owner: Mapped["User"] = relationship("User", back_populates="voice_sessions")

    def __repr__(self):
        return f"<VoiceSession(id={self.id}, owner={self.persona_owner_id}, status={self.status}, duration={self.duration_seconds}s)>"

    __table_args__ = (
        Index("ix_voice_sessions_persona_owner_id", "persona_owner_id"),
        Index("ix_voice_sessions_persona_id", "persona_id"),
        Index("ix_voice_sessions_status", "status"),
        # Composite index for querying owner's usage in a time period
        Index("ix_voice_sessions_owner_started", "persona_owner_id", "started_at"),
        # Index for conversation detail API lookups (links voice sessions to conversations)
        Index("ix_voice_sessions_caller_session_token", "caller_session_token"),
    )
