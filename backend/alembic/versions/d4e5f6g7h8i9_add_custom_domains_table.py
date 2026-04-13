"""add_custom_domains_table

Revision ID: d4e5f6g7h8i9
Revises: a710bf4e715c
Create Date: 2025-12-19 10:00:00.000000

Custom domains for white-label clone deployments (USER-LEVEL).
Allows users to serve their AI clone at custom domains like chat.example.com
using Vercel's domain API for DNS verification and SSL provisioning.

User-level routing:
- customdomain.com → equivalent to myclone.is/username
- customdomain.com/persona_name → equivalent to myclone.is/username/persona_name
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: Union[str, Sequence[str], None] = "a710bf4e715c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create custom_domains table for white-label domain integration (user-level)."""
    # Create the domain_status enum type
    domain_status_enum = postgresql.ENUM(
        "pending",
        "verifying",
        "verified",
        "active",
        "failed",
        "expired",
        name="domain_status",
        create_type=False,
    )

    # Create the enum type first
    domain_status_enum.create(op.get_bind(), checkfirst=True)

    # Create custom_domains table (USER-LEVEL - no persona_id)
    op.create_table(
        "custom_domains",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
            comment="Owner of the custom domain",
        ),
        sa.Column(
            "domain",
            sa.Text(),
            nullable=False,
            comment="Full domain name (e.g., 'chat.example.com' or 'example.com')",
        ),
        sa.Column(
            "verification_records",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="DNS records required for verification (from Vercel API)",
        ),
        sa.Column(
            "routing_record",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="DNS record for routing traffic (A or CNAME)",
        ),
        sa.Column(
            "status",
            domain_status_enum,
            nullable=False,
            server_default="pending",
            comment="Current status of domain setup",
        ),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When domain was verified",
        ),
        sa.Column(
            "ssl_provisioned_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When SSL certificate was provisioned",
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
            comment="Last error message (for failed verifications)",
        ),
        sa.Column(
            "last_check_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last time verification was checked",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_custom_domains_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain", name="uq_custom_domains_domain"),
        comment="Custom domains for white-label clone deployments (user-level)",
    )

    # Create indexes
    op.create_index(
        "idx_custom_domains_user_id",
        "custom_domains",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "idx_custom_domains_domain",
        "custom_domains",
        ["domain"],
        unique=True,
    )
    op.create_index(
        "idx_custom_domains_status",
        "custom_domains",
        ["status"],
        unique=False,
    )
    op.create_index(
        "idx_custom_domains_active",
        "custom_domains",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    """Drop custom_domains table and domain_status enum."""
    # Drop indexes
    op.drop_index(
        "idx_custom_domains_active",
        table_name="custom_domains",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index("idx_custom_domains_status", table_name="custom_domains")
    op.drop_index("idx_custom_domains_domain", table_name="custom_domains")
    op.drop_index("idx_custom_domains_user_id", table_name="custom_domains")

    # Drop table
    op.drop_table("custom_domains")

    # Drop enum type
    domain_status_enum = postgresql.ENUM(
        "pending",
        "verifying",
        "verified",
        "active",
        "failed",
        "expired",
        name="domain_status",
    )
    domain_status_enum.drop(op.get_bind(), checkfirst=True)
