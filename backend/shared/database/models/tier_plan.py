"""
Tier plan models for usage limits, subscriptions, and usage tracking
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from .database import Base

if TYPE_CHECKING:
    from .stripe import PlatformStripeSubscription
    from .user import User


class SubscriptionStatus(str, enum.Enum):
    """Subscription status enum"""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"


class TierPlan(Base):
    """
    Tier plans defining usage limits for different subscription levels.
    Categories:
    1. Raw text files (txt, md) - simple storage tracking
    2. Document files (pdf, docx, xlsx, pptx) - parsing required
    3. Multimedia files (audio, video) - duration + storage tracking
    4. YouTube videos - duration tracking only (no storage)
    Hard limits (cannot be exceeded even in enterprise):
    - Multimedia: 6 hours total duration
    - YouTube: 2 hours max per video, 1000 videos max
    """

    __tablename__ = "tier_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tier_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # Raw text file limits (txt, md)
    max_raw_text_storage_mb: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Max storage for raw text files (txt, md)"
    )
    max_raw_text_files: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Max number of raw text files"
    )
    # Document file limits (pdf, docx, xlsx, pptx, etc)
    max_document_file_size_mb: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Max single document file size"
    )
    max_document_storage_mb: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Total storage for document files"
    )
    max_document_files: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Max number of document files"
    )
    # Multimedia file limits (audio, video) - 6 hours hard duration limit
    max_multimedia_file_size_mb: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Max single multimedia file size"
    )
    max_multimedia_storage_mb: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Total storage for multimedia files"
    )
    max_multimedia_files: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Max number of multimedia files"
    )
    max_multimedia_duration_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Total duration limit (hard limit: 6 hours)"
    )
    # YouTube ingestion limits - duration-based only (no storage)
    max_youtube_videos: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Max YouTube videos (hard limit: 1000)"
    )
    max_youtube_video_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Max single video duration (hard limit: 120 min)"
    )
    max_youtube_total_duration_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Total YouTube duration across all videos"
    )
    # Voice clone limits
    max_voice_clones: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1", comment="Max voice clones (-1 = unlimited)"
    )
    # Voice chat limits (monthly) - charged to PERSONA OWNER
    max_voice_minutes_per_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="10",
        comment="Max voice chat minutes per month (-1 = unlimited)",
    )
    # Text chat limits (monthly) - charged to PERSONA OWNER
    max_text_messages_per_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="500",
        comment="Max text chat messages per month (-1 = unlimited)",
    )
    # Persona limits
    max_personas: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        comment="Max personas per user (-1 = unlimited)",
    )
    # Custom domain limits
    max_custom_domains: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Max custom domains per user (-1 = unlimited)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    # Relationships
    subscriptions: Mapped[list["UserSubscription"]] = relationship(
        "UserSubscription", back_populates="tier_plan"
    )

    def __repr__(self):
        return f"<TierPlan(tier_name='{self.tier_name}')>"

    __table_args__ = (UniqueConstraint("tier_name", name="uq_tier_plans_tier_name"),)


class UserSubscription(Base):
    """
    User subscription tracking - maps users to tier plans.
    Provides:
    - Clean separation between user identity and subscription management
    - Historical tracking capability
    - Easy extensibility for future features (payment info, promos, etc.)
    """

    __tablename__ = "user_subscriptions"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tier_plans.id"), nullable=False, server_default="0"
    )
    subscription_start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    subscription_end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="NULL means lifetime/no expiry"
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(
            SubscriptionStatus,
            name="subscription_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        server_default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    tier_plan: Mapped["TierPlan"] = relationship("TierPlan", back_populates="subscriptions")
    platform_stripe_subscription: Mapped[Optional["PlatformStripeSubscription"]] = relationship(
        back_populates="user_subscription", uselist=False
    )

    def __repr__(self):
        return f"<UserSubscription(user_id={self.user_id}, tier_id={self.tier_id}, status='{self.status}')>"

    __table_args__ = (
        Index("idx_user_subscriptions_user_end_date", "user_id", "subscription_end_date"),
        Index("idx_user_subscriptions_status_end_date", "status", "subscription_end_date"),
        # Unique partial index to ensure only one active subscription per user
        Index(
            "idx_user_subscriptions_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class UserUsageCache(Base):
    """
    Cache calculated usage to avoid expensive aggregations on every upload.
    This table is updated whenever:
    - A document/file is uploaded
    - A YouTube video is ingested
    - A file is deleted
    """

    __tablename__ = "user_usage_cache"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Raw Text Tracking
    raw_text_storage_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Total storage used by raw text files",
    )
    raw_text_file_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", comment="Number of raw text files"
    )
    # Document Tracking
    document_storage_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Total storage used by document files",
    )
    document_file_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", comment="Number of document files"
    )
    # Multimedia Tracking
    multimedia_storage_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Total storage used by multimedia files",
    )
    multimedia_file_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", comment="Number of multimedia files"
    )
    multimedia_total_duration_seconds: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Total duration of multimedia files in seconds",
    )
    # YouTube Tracking
    youtube_video_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", comment="Number of YouTube videos ingested"
    )
    youtube_total_duration_seconds: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Total duration of YouTube videos in seconds",
    )
    # Voice Chat Tracking
    voice_seconds_used: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Voice chat seconds used in current period",
    )
    voice_usage_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When voice usage resets (monthly)",
    )
    # Text Chat Tracking
    text_messages_used: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Text chat messages used in current period",
    )
    text_usage_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When text usage resets (monthly)",
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="usage_cache")

    def __repr__(self):
        return f"<UserUsageCache(user_id={self.user_id})>"

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_usage_cache_user_id"),
        Index("idx_user_usage_cache_user_id", "user_id"),
    )
