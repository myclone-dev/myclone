"""create_custom_email_domains_table

Revision ID: b426ae7098dd
Revises: 1aa7dbeebdfb
Create Date: 2026-01-26 06:58:04.681388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b426ae7098dd'
down_revision: Union[str, Sequence[str], None] = '6799ef3448b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define the enum type - use create_type=False to avoid creating if exists
email_domain_status_enum = postgresql.ENUM(
    'pending', 'verifying', 'verified', 'failed',
    name='email_domain_status',
    create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    # Create the enum type if it doesn't exist
    connection = op.get_bind()
    result = connection.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'email_domain_status'")
    )
    if not result.fetchone():
        email_domain_status_enum.create(connection, checkfirst=True)

    # Create the table
    op.create_table('custom_email_domains',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False, comment='Unique identifier for the custom email domain'),
        sa.Column('user_id', sa.UUID(), nullable=False, comment='Owner of the custom email domain'),
        sa.Column('domain', sa.String(length=255), nullable=False, comment="The email domain (e.g., 'acme.com')"),
        sa.Column('from_email', sa.String(length=255), nullable=False, comment="The sender email address (e.g., 'hello@acme.com')"),
        sa.Column('from_name', sa.String(length=255), nullable=True, comment="The sender display name (e.g., 'Acme Support')"),
        sa.Column('reply_to_email', sa.String(length=255), nullable=True, comment='Optional reply-to email address'),
        sa.Column('resend_domain_id', sa.String(length=255), nullable=True, comment='Domain ID from Resend API'),
        sa.Column('resend_api_key', sa.Text(), nullable=True, comment="Optional: Customer's own Resend API key (encrypted)"),
        sa.Column('status', email_domain_status_enum, nullable=False, comment='Current verification status of the domain'),
        sa.Column('dns_records', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='DNS records required for verification (SPF, DKIM, MX)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, comment='When the domain was added'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, comment='When the domain was last updated'),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True, comment='When the domain was successfully verified'),
        sa.Column('last_verification_attempt', sa.DateTime(timezone=True), nullable=True, comment='When verification was last attempted'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Custom email domains for whitelabel email sending (enterprise feature)'
    )
    op.create_index('idx_custom_email_domains_domain', 'custom_email_domains', ['domain'], unique=True)
    op.create_index('idx_custom_email_domains_status', 'custom_email_domains', ['status'], unique=False)
    op.create_index('idx_custom_email_domains_user_id', 'custom_email_domains', ['user_id'], unique=False)
    op.create_index('idx_custom_email_domains_user_verified', 'custom_email_domains', ['user_id'], unique=False, postgresql_where=sa.text("status = 'verified'"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_custom_email_domains_user_verified', table_name='custom_email_domains', postgresql_where=sa.text("status = 'verified'"))
    op.drop_index('idx_custom_email_domains_user_id', table_name='custom_email_domains')
    op.drop_index('idx_custom_email_domains_status', table_name='custom_email_domains')
    op.drop_index('idx_custom_email_domains_domain', table_name='custom_email_domains')
    op.drop_table('custom_email_domains')
    # Don't drop the enum type in case other migrations use it
