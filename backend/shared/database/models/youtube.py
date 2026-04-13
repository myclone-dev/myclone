"""
YouTube data models
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from .database import Base

if TYPE_CHECKING:
    from .user import User


class YouTubeVideo(Base):
    """
    YouTube videos - raw data only, embeddings stored in content_chunks
    """

    __tablename__ = "youtube_videos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    video_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    video_url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    view_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    channel_name: Mapped[Optional[str]] = mapped_column(Text)
    channel_url: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="youtube_videos")

    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_youtube_videos_user_video_id"),
        Index("idx_youtube_videos_user_id", "user_id"),
        Index("idx_youtube_videos_published_at", text("published_at DESC")),
        Index("idx_youtube_videos_video_id", "video_id"),
        {"comment": "YouTube videos - raw data only, embeddings stored in content_chunks"},
    )
