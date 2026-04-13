"""Conversation Attachment model for storing chat file attachments."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ExtractionStatus(str, Enum):
    """Status of text extraction from attachment."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionMethod(str, Enum):
    """Method used to extract text from attachment."""

    MARKER_API = "marker_api"
    GPT4_VISION = "gpt4_vision"
    NONE = "none"


class ConversationAttachment(Base):
    """
    Model for storing chat conversation attachments (PDFs, images).

    Attachments are uploaded to S3 and linked to conversations.
    Text is extracted using appropriate methods (Marker API for PDFs, GPT-4o Vision for images).
    """

    __tablename__ = "conversation_attachments"
    __table_args__ = (
        Index("idx_conv_attachments_conversation", "conversation_id"),
        Index("idx_conv_attachments_session", "session_token"),
        Index("idx_conv_attachments_status", "extraction_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Linking - conversation_id is nullable because attachment may be uploaded before message is sent
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        comment="FK to conversations - NULL until message with attachment is sent",
    )
    session_token: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Session token for grouping attachments before conversation exists",
    )
    message_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Position in conversation messages array (NULL until message sent)",
    )

    # File metadata
    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Sanitized filename stored in S3",
    )
    original_filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Original filename as uploaded by user",
    )
    file_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="File type: pdf, png, jpg, jpeg",
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes",
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="MIME type of the file",
    )

    # S3 Storage
    s3_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Full S3 URL/path to the file",
    )
    s3_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="S3 object key (path within bucket)",
    )

    # Extracted content for RAG
    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Text extracted from the attachment (for RAG context)",
    )
    extraction_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Method used: marker_api, gpt4_vision, none",
    )
    extraction_status: Mapped[str] = mapped_column(
        String(50),
        default=ExtractionStatus.PENDING.value,
        comment="Status: pending, processing, completed, failed",
    )
    extraction_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if extraction failed",
    )

    # Additional metadata
    attachment_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        comment="Additional metadata: page_count, dimensions, etc.",
    )

    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        comment="When the file was uploaded",
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When text extraction completed",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    conversation: Mapped[Optional["Conversation"]] = relationship(  # noqa: F821
        "Conversation",
        back_populates="attachments",
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationAttachment(id={self.id}, "
            f"filename={self.original_filename}, "
            f"type={self.file_type}, "
            f"status={self.extraction_status})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id) if self.conversation_id else None,
            "session_token": self.session_token,
            "message_index": self.message_index,
            "filename": self.original_filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "s3_url": self.s3_url,
            "extraction_status": self.extraction_status,
            "extraction_method": self.extraction_method,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "metadata": self.attachment_metadata or {},
        }

    def to_message_dict(self) -> dict:
        """Convert to dictionary format for embedding in message JSONB."""
        return {
            "id": str(self.id),
            "filename": self.original_filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "s3_url": self.s3_url,
        }
