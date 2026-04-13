"""
Custom Domain model for white-label domain integration

Allows users to connect custom domains to their MyClone profile,
enabling their AI clone to be hosted at their own domain (e.g., chat.example.com)

User-level domains:
- customdomain.com → equivalent to myclone.is/username
- customdomain.com/persona_name → equivalent to myclone.is/username/persona_name
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from .database import Base

if TYPE_CHECKING:
    from .user import User


class DomainStatus(str, Enum):
    """Status of custom domain verification and setup"""

    PENDING = "pending"  # Domain added, awaiting DNS configuration
    VERIFYING = "verifying"  # DNS check in progress
    VERIFIED = "verified"  # DNS verified, SSL being provisioned
    ACTIVE = "active"  # Fully configured and serving traffic
    FAILED = "failed"  # Verification failed
    EXPIRED = "expired"  # Verification expired (user didn't add DNS records)


class CustomDomain(Base):
    """
    Custom domains for white-label clone deployments (USER-LEVEL)

    Allows users to serve their AI clone at custom domains like:
    - chat.example.com (subdomain)
    - example.com (apex domain)

    This is a USER-LEVEL feature:
    - customdomain.com → routes to /username (shows all personas)
    - customdomain.com/persona_name → routes to /username/persona_name

    Integration with Vercel:
    - Uses Vercel's domain API to add/verify domains
    - Vercel handles SSL certificate provisioning automatically
    - DNS verification via TXT records

    Flow:
    1. User adds domain in dashboard
    2. Backend calls Vercel API to add domain to project
    3. User sees DNS records to add (TXT + A/CNAME)
    4. User adds DNS records at their registrar
    5. Backend calls Vercel verify endpoint
    6. Once verified, Vercel provisions SSL
    7. Domain becomes active

    Verification records stored in JSON format:
    {
        "type": "TXT",
        "name": "_vercel",
        "value": "vc-domain-verify=example.com,abc123..."
    }
    """

    __tablename__ = "custom_domains"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    # Owner relationship - domain is linked to user, not persona
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Owner of the custom domain",
    )

    # Domain information
    domain: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        comment="Full domain name (e.g., 'chat.example.com' or 'example.com')",
    )

    # Verification records (JSON array from Vercel API)
    # Example: [{"type": "TXT", "name": "_vercel", "value": "vc-domain-verify=..."}]
    verification_records: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="DNS records required for verification (from Vercel API)",
    )

    # A record for routing (Vercel's IP)
    # For apex domains: A record pointing to 76.76.21.21
    # For subdomains: CNAME to cname.vercel-dns.com
    routing_record: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="DNS record for routing traffic (A or CNAME)",
    )

    # Status tracking
    status: Mapped[DomainStatus] = mapped_column(
        SQLEnum(
            DomainStatus,
            name="domain_status",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=DomainStatus.PENDING,
        nullable=False,
        comment="Current status of domain setup",
    )

    # Verification tracking
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When domain was verified",
    )

    ssl_provisioned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When SSL certificate was provisioned",
    )

    # Error tracking
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Last error message (for failed verifications)",
    )

    last_check_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time verification was checked",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships - user-level only, no persona relationship
    user: Mapped["User"] = relationship("User", back_populates="custom_domains")

    __table_args__ = (
        Index("idx_custom_domains_user_id", "user_id"),
        Index("idx_custom_domains_domain", "domain", unique=True),
        Index("idx_custom_domains_status", "status"),
        Index(
            "idx_custom_domains_active",
            "user_id",
            postgresql_where=text("status = 'active'"),
        ),
        {"comment": "Custom domains for white-label clone deployments (user-level)"},
    )

    @property
    def is_active(self) -> bool:
        """Check if domain is fully configured and active"""
        return self.status == DomainStatus.ACTIVE

    @property
    def is_verified(self) -> bool:
        """Check if domain ownership is verified (fully active)"""
        return self.status == DomainStatus.ACTIVE

    @property
    def is_apex(self) -> bool:
        """Check if this is an apex (root) domain"""
        # Apex domain has no subdomain (e.g., example.com vs chat.example.com)
        parts = self.domain.split(".")
        # Simple check: apex domains have 2 parts (example.com)
        # Subdomains have 3+ parts (chat.example.com, www.example.com)
        return len(parts) == 2

    def get_dns_instructions(self) -> dict:
        """
        Get human-readable DNS instructions for the user

        Returns dict with:
        - verification: Instructions for TXT record
        - routing: Instructions for A or CNAME record
        """
        instructions = {
            "verification": None,
            "routing": None,
        }

        if self.verification_records:
            # TXT record for verification
            for record in self.verification_records:
                if record.get("type") == "TXT":
                    instructions["verification"] = {
                        "type": "TXT",
                        "name": record.get("name", "_vercel"),
                        "value": record.get("value", ""),
                        "description": "Add this TXT record to verify domain ownership",
                    }
                    break

        if self.routing_record:
            # A or CNAME record for routing
            instructions["routing"] = {
                "type": self.routing_record.get("type", "A"),
                "name": self.routing_record.get("name", "@"),
                "value": self.routing_record.get("value", "76.76.21.21"),
                "description": (
                    "Add this A record to route traffic to your clone"
                    if self.is_apex
                    else "Add this CNAME record to route traffic to your clone"
                ),
            }

        return instructions
