"""
Persona Access Control Models
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from shared.database.base import Base

if TYPE_CHECKING:
    from shared.database.models.database import Persona
    from shared.database.models.user import User


class VisitorWhitelist(Base):
    """
    Global visitor whitelist - user-level

    Each user maintains a whitelist of visitors who can access their private personas.
    Visitors can be assigned to multiple personas (many-to-many via PersonaVisitor).
    """

    __tablename__ = "visitor_whitelist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    # Collected during OTP or manually added by user
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    # Track most recent access to any persona
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # User's notes about this visitor (e.g., 'VIP client', 'Team member')
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship()
    persona_visitors: Mapped[list["PersonaVisitor"]] = relationship(
        back_populates="visitor", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "email", name="uq_visitor_whitelist_user_email"),
        Index("idx_visitor_whitelist_user", "user_id"),
        Index("idx_visitor_whitelist_email", "user_id", "email"),
    )


class PersonaVisitor(Base):
    """
    Junction table for many-to-many relationship between personas and visitors

    Maps which visitors can access which personas.
    """

    __tablename__ = "persona_visitors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitor_whitelist.id", ondelete="CASCADE"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(back_populates="persona_visitors")
    visitor: Mapped["VisitorWhitelist"] = relationship(back_populates="persona_visitors")

    __table_args__ = (
        UniqueConstraint("persona_id", "visitor_id", name="uq_persona_visitors_persona_visitor"),
        Index("idx_persona_visitors_persona", "persona_id"),
        Index("idx_persona_visitors_visitor", "visitor_id"),
    )


class PersonaAccessOTP(Base):
    """
    OTP (One-Time Password) verification for persona access

    Stores temporary OTP codes sent via email for visitor verification.
    """

    __tablename__ = "persona_access_otps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    # 6-digit OTP code
    otp_code: Mapped[str] = mapped_column(String(6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    # OTP expires after 5 minutes
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # When OTP was successfully verified
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, server_default="3", nullable=False)

    # Relationships
    persona: Mapped["Persona"] = relationship()

    __table_args__ = (
        CheckConstraint("attempts <= max_attempts", name="ck_persona_access_otps_max_attempts"),
        Index("idx_persona_access_otps_lookup", "persona_id", "email", "otp_code"),
        Index("idx_persona_access_otps_expires", "expires_at"),
    )
