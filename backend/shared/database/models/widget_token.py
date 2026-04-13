"""
Widget Token model for chat widget authentication
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from .database import Base

if TYPE_CHECKING:
    from .user import User


class WidgetToken(Base):
    """
    Widget authentication tokens for chat widget

    Allows users to embed chat widgets on multiple websites with separate tokens.
    Each token is a JWT containing user_id and username for authentication.
    """

    __tablename__ = "widget_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(
        Text, nullable=False, unique=True, comment="JWT token prefixed with wgt_"
    )
    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Token name for identification (e.g., 'Main Website', 'Blog Widget')",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Optional description with additional details"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Last time this token was used"
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When token was revoked (null = active)"
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="widget_tokens")

    __table_args__ = (
        Index("idx_widget_tokens_user_id", "user_id"),
        Index("idx_widget_tokens_token", "token", unique=True),
        Index(
            "idx_widget_tokens_active",
            "user_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        {"comment": "Widget authentication tokens for chat widget embedding"},
    )

    @property
    def is_active(self) -> bool:
        """Check if token is active (not revoked)"""
        return self.revoked_at is None
