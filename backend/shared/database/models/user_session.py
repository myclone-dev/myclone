from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.models.database import Base

if TYPE_CHECKING:
    from shared.database.models.database import Persona


class UserSession(Base):
    """User session model for email-based session management"""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_email: Mapped[str] = mapped_column(String(255))
    session_token: Mapped[str] = mapped_column(String(500), unique=True)
    persona_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE")
    )
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_accessed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc) + timedelta(days=7)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    session_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    persona: Mapped[Optional[Persona]] = relationship(back_populates="user_sessions")

    # Indexes
    __table_args__ = (
        Index("idx_user_sessions_user_email", "user_email"),
        Index("idx_user_sessions_session_token", "session_token"),
        Index("idx_user_sessions_persona_id", "persona_id"),
        Index("idx_user_sessions_expires_at", "expires_at"),
        Index("idx_user_sessions_active", "is_active"),
    )

    @property
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if session is active and not expired"""
        return self.is_active and not self.is_expired

    def extend_session(self, days: int = 7):
        """Extend session expiry"""
        self.expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        self.last_accessed = datetime.now(timezone.utc)

    def deactivate(self):
        """Deactivate session"""
        self.is_active = False
