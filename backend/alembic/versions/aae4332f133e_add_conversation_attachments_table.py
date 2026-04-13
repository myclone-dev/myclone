"""add_conversation_attachments_table

Revision ID: aae4332f133e
Revises: 10ad9fd2fe04
Create Date: 2025-12-15 15:58:30.242049

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "aae4332f133e"
down_revision: Union[str, Sequence[str], None] = "10ad9fd2fe04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create conversation_attachments table for storing chat file attachments."""
    op.create_table(
        "conversation_attachments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "conversation_id",
            sa.UUID(),
            nullable=True,
            comment="FK to conversations - NULL until message with attachment is sent",
        ),
        sa.Column(
            "session_token",
            sa.String(length=255),
            nullable=False,
            comment="Session token for grouping attachments before conversation exists",
        ),
        sa.Column(
            "message_index",
            sa.Integer(),
            nullable=True,
            comment="Position in conversation messages array (NULL until message sent)",
        ),
        sa.Column(
            "filename",
            sa.String(length=500),
            nullable=False,
            comment="Sanitized filename stored in S3",
        ),
        sa.Column(
            "original_filename",
            sa.String(length=500),
            nullable=False,
            comment="Original filename as uploaded by user",
        ),
        sa.Column(
            "file_type",
            sa.String(length=50),
            nullable=False,
            comment="File type: pdf, png, jpg, jpeg",
        ),
        sa.Column(
            "file_size",
            sa.Integer(),
            nullable=False,
            comment="File size in bytes",
        ),
        sa.Column(
            "mime_type",
            sa.String(length=100),
            nullable=False,
            comment="MIME type of the file",
        ),
        sa.Column(
            "s3_url",
            sa.String(length=1000),
            nullable=False,
            comment="Full S3 URL/path to the file",
        ),
        sa.Column(
            "s3_key",
            sa.String(length=500),
            nullable=False,
            comment="S3 object key (path within bucket)",
        ),
        sa.Column(
            "extracted_text",
            sa.Text(),
            nullable=True,
            comment="Text extracted from the attachment (for RAG context)",
        ),
        sa.Column(
            "extraction_method",
            sa.String(length=50),
            nullable=True,
            comment="Method used: marker_api, gpt4_vision, none",
        ),
        sa.Column(
            "extraction_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
            comment="Status: pending, processing, completed, failed",
        ),
        sa.Column(
            "extraction_error",
            sa.Text(),
            nullable=True,
            comment="Error message if extraction failed",
        ),
        sa.Column(
            "attachment_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
            comment="Additional metadata: page_count, dimensions, etc.",
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="When the file was uploaded",
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When text extraction completed",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_conv_attachments_conversation",
        "conversation_attachments",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "idx_conv_attachments_session",
        "conversation_attachments",
        ["session_token"],
        unique=False,
    )
    op.create_index(
        "idx_conv_attachments_status",
        "conversation_attachments",
        ["extraction_status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop conversation_attachments table."""
    op.drop_index("idx_conv_attachments_status", table_name="conversation_attachments")
    op.drop_index("idx_conv_attachments_session", table_name="conversation_attachments")
    op.drop_index(
        "idx_conv_attachments_conversation", table_name="conversation_attachments"
    )
    op.drop_table("conversation_attachments")
