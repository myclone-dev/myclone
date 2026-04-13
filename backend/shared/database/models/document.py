"""
Document storage models (PDF, Excel, PowerPoint, etc.)
Note: Generated columns (page_count, sheet_count, slide_count) are created via migration SQL
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from .database import Base

if TYPE_CHECKING:
    from .user import User


class Document(Base):
    """
    All document types - raw data only, embeddings stored in content_chunks
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    content_text: Mapped[Optional[str]] = mapped_column(Text)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    document_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default="{}", nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Generated columns (read-only, computed in DB)
    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        Computed(
            "CASE WHEN metadata ? 'page_count' THEN (metadata->>'page_count')::int ELSE NULL END",
            persisted=True,
        ),
    )
    sheet_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        Computed(
            "CASE WHEN metadata ? 'sheet_count' THEN (metadata->>'sheet_count')::int ELSE NULL END",
            persisted=True,
        ),
    )
    slide_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        Computed(
            "CASE WHEN metadata ? 'slide_count' THEN (metadata->>'slide_count')::int ELSE NULL END",
            persisted=True,
        ),
    )
    checksum: Mapped[Optional[str]] = mapped_column(
        Text,
        Computed(
            "metadata->>'checksum'",
            persisted=True,
        ),
        nullable=True,  # Explicitly set nullable=True for existing documents
        comment="SHA-256 checksum of file content for duplicate detection. NULL for documents without checksum in metadata. Duplicate detection is per-user (user_id + checksum combination).",
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="documents")

    __table_args__ = (
        CheckConstraint(
            "document_type IN ('pdf', 'xlsx', 'pptx', 'docx', 'csv', 'txt', 'md', 'mp3', 'mp4', 'webm', 'wav', 'avi', 'm4a', 'mov', 'mkv')",
            name="ck_documents_valid_type",
        ),
        CheckConstraint(
            "document_type != 'pdf' OR (metadata ? 'page_count' AND page_count > 0)",
            name="ck_documents_valid_pdf_metadata",
        ),
        CheckConstraint(
            "document_type != 'xlsx' OR (metadata ? 'sheet_count' AND sheet_count > 0)",
            name="ck_documents_valid_excel_metadata",
        ),
        CheckConstraint(
            "document_type != 'pptx' OR (metadata ? 'slide_count' AND slide_count > 0)",
            name="ck_documents_valid_pptx_metadata",
        ),
        Index("idx_documents_user_id", "user_id"),
        Index("idx_documents_type", "document_type"),
        Index(
            "idx_documents_pdf_pages",
            "page_count",
            postgresql_where=text("document_type = 'pdf' AND page_count IS NOT NULL"),
        ),
        Index(
            "idx_documents_excel_sheets",
            "sheet_count",
            postgresql_where=text("document_type = 'xlsx' AND sheet_count IS NOT NULL"),
        ),
        Index(
            "idx_documents_pptx_slides",
            "slide_count",
            postgresql_where=text("document_type = 'pptx' AND slide_count IS NOT NULL"),
        ),
        Index(
            "idx_documents_checksum_user",
            "user_id",
            "checksum",
            postgresql_where=text("checksum IS NOT NULL"),
        ),
        {"comment": "All document types - raw data only, embeddings stored in content_chunks"},
    )
