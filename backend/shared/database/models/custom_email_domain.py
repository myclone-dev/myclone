"""
Custom Email Domain model for whitelabel email sending.

Allows enterprise users to send verification/OTP emails from their own domain
instead of the default myclone.is domain.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey
from sqlalchemy.sql import text

from .database import Base

if TYPE_CHECKING:
    from .user import User


class EmailDomainStatus(str, Enum):
    """Status of custom email domain verification."""

    PENDING = "pending"  # Domain added, DNS records not yet configured
    VERIFYING = "verifying"  # DNS verification in progress
    VERIFIED = "verified"  # Domain verified and ready to use
    FAILED = "failed"  # Verification failed (DNS records not found within 72h)


class CustomEmailDomain(Base):
    """
    Stores custom email domains for whitelabel email sending.

    Enterprise users can configure their own domain to send verification
    and OTP emails from their brand instead of myclone.is.
    """

    __tablename__ = "custom_email_domains"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Unique identifier for the custom email domain",
    )

    # Owner relationship
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Owner of the custom email domain",
    )

    # Domain configuration
    domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="The email domain (e.g., 'acme.com')",
    )

    from_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="The sender email address (e.g., 'hello@acme.com')",
    )

    from_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="The sender display name (e.g., 'Acme Support')",
    )

    reply_to_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional reply-to email address",
    )

    # Resend integration
    resend_domain_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Domain ID from Resend API",
    )

    resend_api_key: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional: Customer's own Resend API key (encrypted)",
    )

    # Verification status
    status: Mapped[EmailDomainStatus] = mapped_column(
        SQLEnum(
            EmailDomainStatus,
            name="email_domain_status",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=EmailDomainStatus.PENDING,
        nullable=False,
        comment="Current verification status of the domain",
    )

    # DNS records from Resend (SPF, DKIM, MX)
    dns_records: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="DNS records required for verification (SPF, DKIM, MX)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="When the domain was added",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="When the domain was last updated",
    )

    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the domain was successfully verified",
    )

    last_verification_attempt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When verification was last attempted",
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="custom_email_domains")

    # Indexes and constraints
    __table_args__ = (
        # User lookup
        Index("idx_custom_email_domains_user_id", "user_id"),
        # Domain uniqueness (globally unique - no two users can have same domain)
        Index("idx_custom_email_domains_domain", "domain", unique=True),
        # Status filtering
        Index("idx_custom_email_domains_status", "status"),
        # Quick lookup for verified domains by user
        Index(
            "idx_custom_email_domains_user_verified",
            "user_id",
            postgresql_where=text("status = 'verified'"),
        ),
        {"comment": "Custom email domains for whitelabel email sending (enterprise feature)"},
    )

    @property
    def is_verified(self) -> bool:
        """Check if domain is verified and ready to use."""
        return self.status == EmailDomainStatus.VERIFIED

    @property
    def is_pending(self) -> bool:
        """Check if domain is pending verification."""
        return self.status in (EmailDomainStatus.PENDING, EmailDomainStatus.VERIFYING)

    @property
    def sender_address(self) -> str:
        """Get the formatted sender address for email headers."""
        if self.from_name:
            return f"{self.from_name} <{self.from_email}>"
        return self.from_email

    def __repr__(self) -> str:
        return f"<CustomEmailDomain {self.domain} ({self.status.value})>"
