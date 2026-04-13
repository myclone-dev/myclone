"""
Text Session Model - Tracks text chat sessions

Separate from voice_sessions for clean separation:
- Text sessions track message_count (not duration)
- No recording fields (egress_id, recording_status)
- Optimized for text-specific analytics
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from shared.database.base import Base

if TYPE_CHECKING:
    from .database import Persona
    from .user import User


class TextSession(Base):
    """Text chat session tracking

    Tracks text-only chat sessions through LiveKit (text_only_mode=true).
    Similar to voice_sessions but optimized for text:
    - message_count instead of duration_seconds
    - No recording fields (egress_id, recording_status)
    - Links to persona owner for quota tracking
    """

    __tablename__ = "text_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    # Persona relationship
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Owner who gets charged (persona owner)
    persona_owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User who owns the persona (gets charged)",
    )

    # Session details
    room_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="LiveKit room name",
    )

    message_count: Mapped[int] = mapped_column(
        Integer,
        server_default="0",
        nullable=False,
        comment="Total messages sent in this session",
    )

    session_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="User session token for linking to user_sessions",
    )

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When session ended (NULL = active)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    # Relationships
    persona: Mapped["Persona"] = relationship("Persona", foreign_keys=[persona_id])
    owner: Mapped["User"] = relationship("User", foreign_keys=[persona_owner_id])

    __table_args__ = (
        Index("idx_text_sessions_persona_id", "persona_id"),
        Index("idx_text_sessions_owner_id", "persona_owner_id"),
        Index("idx_text_sessions_room_name", "room_name"),
        Index("idx_text_sessions_started_at", "started_at"),
        # Partial index for active sessions
        Index(
            "idx_text_sessions_active",
            "ended_at",
            postgresql_where=text("ended_at IS NULL"),
        ),
        {"comment": "Text chat session tracking (separate from voice_sessions)"},
    )

    def __repr__(self):
        return f"<TextSession(id={self.id}, persona_id={self.persona_id}, message_count={self.message_count})>"
