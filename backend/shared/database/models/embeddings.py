"""
Voyage AI embeddings table model (512 dimensions).

This model represents the `data_llamalite_embeddings` table used for Voyage AI embeddings.
"""

import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class VoyageLiteEmbedding(Base):
    """
    Model for Voyage AI embeddings table (512 dimensions).

    This table uses 512-dimensional vectors from Voyage AI embedding model.

    Core Columns:
    - id: Auto-incrementing primary key
    - text: The actual text content chunk
    - metadata_: JSONB containing all metadata
    - node_id: Internal node identifier
    - embedding: Vector representation of the text (512 dimensions for Voyage AI)

    Custom Columns:
    - user_id: Which user owns this embedding
    - source_record_id: Generic FK to source record (linkedin_basic_info.id, twitter_posts.id, etc.)
    - source: Source platform where data originated (linkedin, twitter, website, document)
    - source_type: Content type within that platform (profile, post, tweet, page, experience)
    - posted_at: When content was posted (NULL for profile/static content)
    - created_at: When embedding was created
    - text_search_tsv: Full-text search vector (auto-populated by trigger)
    """

    __tablename__ = "data_llamalite_embeddings"

    # ============================================================================
    # LlamaIndex Default Columns
    # ============================================================================
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata_", JSONB)
    node_id: Mapped[Optional[str]] = mapped_column(String)
    embedding: Mapped[Optional[Vector]] = mapped_column(
        Vector(512)
    )  # Voyage embedding 512 dimensions

    # ============================================================================
    # Custom Columns (for analytics and direct SQL queries)
    # ============================================================================
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="User who owns this embedding (populated after insertion)",
    )
    source_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Generic FK to source record (populated after insertion)",
    )
    source: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Source platform (populated after insertion)"
    )
    source_type: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Type of content (populated after insertion)",
    )
    posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When content was posted (NULL for profile/static content)",
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When embedding was created"
    )
    text_search_tsv: Mapped[Optional[str]] = mapped_column(
        TSVECTOR,
        nullable=True,
        comment="Full-text search vector (auto-populated by trigger)",
    )

    __table_args__ = {"extend_existing": True}
