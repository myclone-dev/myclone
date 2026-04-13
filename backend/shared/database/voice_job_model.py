"""
Voice Processing Job model shared between backend and workers.

This module provides the VoiceProcessingJob SQLAlchemy model and database session factory
that is used by both the backend API and worker containers for shared job state management.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

# Import shared Base
from shared.database.base import Base


class VoiceProcessingJob(Base):
    """SQLAlchemy model for voice processing jobs stored in PostgreSQL.

    This model provides shared state between the backend API and worker containers,
    replacing the in-memory dictionary that caused job state isolation issues.
    """

    __tablename__ = "voice_processing_jobs"

    # Primary identifiers
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Job configuration
    job_type: Mapped[str] = mapped_column(
        String(50)
    )  # VOICE_EXTRACTION, TRANSCRIPT_EXTRACTION, etc.
    status: Mapped[str] = mapped_column(
        String(50), default="pending", index=True
    )  # pending, processing, completed, failed, cancelled
    priority: Mapped[str] = mapped_column(
        String(20), default="normal"
    )  # low, normal, high, critical

    # Request and result data (JSONB for efficient querying and flexibility)
    request_data: Mapped[dict] = mapped_column(JSONB)  # Complete JobRequest serialized
    result: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # Result data with file paths, metadata, etc.

    # Progress tracking
    current_stage: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # downloading, extracting, processing, etc.
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0)
    stage_details: Mapped[Optional[dict]] = mapped_column(JSONB)  # Stage-specific progress info

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_code: Mapped[Optional[str]] = mapped_column(String(50))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    worker_id: Mapped[Optional[str]] = mapped_column(
        String(255)
    )  # Which worker is processing this job

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# Database connection setup - use shared config
from shared.database.config import get_database_url

DATABASE_URL = get_database_url()

# Only create engine if DATABASE_URL is set (allows alembic checks without DB)
engine = None
async_session_maker = None

if DATABASE_URL:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
