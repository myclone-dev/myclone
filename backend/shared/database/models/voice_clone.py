"""
Voice clone storage models for ElevenLabs voice samples
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from .database import Base

if TYPE_CHECKING:
    from .user import User


class VoiceClone(Base):
    """
    Voice clone samples uploaded to ElevenLabs
    Stores metadata and S3 paths for voice clone audio files
    """

    __tablename__ = "voice_clones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    voice_id: Mapped[str] = mapped_column(Text, nullable=False, comment="ElevenLabs voice ID")
    name: Mapped[str] = mapped_column(Text, nullable=False, comment="Voice clone name")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platform: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="elevenlabs",
        comment="Voice platform used: elevenlabs, playht, cartesia, or custom",
    )
    model: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Model identifier for the voice clone"
    )

    # S3 storage paths for voice samples (list of file metadata dicts)
    sample_files: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        comment="Array of S3 paths and metadata for uploaded voice samples",
        server_default="[]",
    )

    # ElevenLabs processing settings
    settings: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Voice clone settings (remove_background_noise, etc.)",
        server_default="{}",
    )

    # File statistics
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="voice_clones")

    __table_args__ = (
        Index("idx_voice_clones_user_id", "user_id"),
        Index("idx_voice_clones_voice_id", "voice_id"),
        Index("idx_voice_clones_created_at", "created_at"),
        Index("idx_voice_clones_platform", "platform"),
        UniqueConstraint("voice_id", name="uq_voice_clones_voice_id"),
        {
            "comment": "Voice clone samples uploaded to ElevenLabs with S3 storage paths for audit trail"
        },
    )
