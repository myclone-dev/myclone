"""
Persona data source mapping model.

Defines which knowledge sources (documents, YouTube videos, etc.) each persona uses.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from .database import Base

if TYPE_CHECKING:
    from .database import Persona


class PersonaDataSource(Base):
    """
    Defines which data sources each persona uses.
    """

    __tablename__ = "persona_data_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Generic FK to source record (documents.id, youtube_videos.id, etc.)",
    )
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    source_filters: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    enabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    persona: Mapped["Persona"] = relationship(back_populates="data_sources")

    __table_args__ = (
        UniqueConstraint(
            "persona_id",
            "source_type",
            "source_record_id",
            name="uq_persona_data_sources_persona_source",
        ),
        CheckConstraint(
            "source_type IN ('linkedin', 'twitter', 'website', 'pdf', 'github', 'medium', 'youtube', 'document')",
            name="ck_persona_data_sources_valid_source_type",
        ),
        Index("idx_persona_data_sources_persona", "persona_id"),
        Index("idx_persona_data_sources_enabled", "persona_id", "enabled"),
        Index("idx_persona_data_sources_source", "source_type"),
        Index("idx_persona_data_sources_source_record", "source_record_id"),
        {"comment": "Defines which data sources each persona uses"},
    )
