"""extend auth_details for password authentication

Revision ID: 57501ffb6332
Revises: 006b0f34361e
Create Date: 2025-11-06 09:30:08.273787

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '57501ffb6332'
down_revision: Union[str, Sequence[str], None] = '006b0f34361e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Extend auth_details table for password authentication.

    This migration:
    1. Adds auth_type field to distinguish between OAuth and password auth
    2. Migrates existing OAuth records to use new auth_type format
    3. Adds password-specific fields (hashed_password, reset tokens, lockout tracking)
    4. Makes OAuth fields nullable (only used for OAuth auth types)
    5. Adds constraints to ensure data integrity
    """

    # Step 1: Add auth_type column (nullable initially for data migration)
    op.add_column('auth_details', sa.Column('auth_type', sa.Text(), nullable=True))

    # Step 2: Data migration - Populate auth_type from existing platform field
    # Existing records have platform='linkedin' or 'google', convert to 'linkedin_oauth' or 'google_oauth'
    op.execute("""
        UPDATE auth_details
        SET auth_type = CONCAT(platform, '_oauth')
        WHERE platform IS NOT NULL
    """)

    # Step 3: Make auth_type NOT NULL now that data is populated
    op.alter_column('auth_details', 'auth_type', nullable=False)

    # Step 4: Add password-specific fields (all nullable)
    op.add_column('auth_details', sa.Column('hashed_password', sa.Text(), nullable=True))
    op.add_column('auth_details', sa.Column('email_verification_token', sa.Text(), nullable=True))
    op.add_column('auth_details', sa.Column('email_verification_token_expires', sa.DateTime(timezone=True), nullable=True))
    op.add_column('auth_details', sa.Column('password_reset_token', sa.Text(), nullable=True))
    op.add_column('auth_details', sa.Column('password_reset_expires', sa.DateTime(timezone=True), nullable=True))
    op.add_column('auth_details', sa.Column('failed_login_attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('auth_details', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('auth_details', sa.Column('last_password_change', sa.DateTime(timezone=True), nullable=True))
    op.add_column('auth_details', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))

    # Step 5: Make OAuth fields nullable (only used for OAuth auth types)
    op.alter_column('auth_details', 'platform', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('auth_details', 'platform_user_id', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('auth_details', 'platform_username', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('auth_details', 'avatar', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('auth_details', 'access_token', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('auth_details', 'token_expiry', existing_type=postgresql.TIMESTAMP(timezone=True), nullable=True)

    # Step 6: Drop old constraint and create new ones
    op.drop_constraint('uq_auth_details_user_platform', 'auth_details', type_='unique')
    op.drop_constraint('ck_auth_details_valid_platform', 'auth_details', type_='check')
    op.create_unique_constraint('uq_auth_details_user_auth_type', 'auth_details', ['user_id', 'auth_type'])

    # Step 7: Add check constraints
    op.create_check_constraint(
        'ck_auth_details_valid_auth_type',
        'auth_details',
        "auth_type IN ('linkedin_oauth', 'google_oauth', 'password')"
    )
    op.create_check_constraint(
        'ck_auth_details_oauth_requires_token',
        'auth_details',
        "(auth_type NOT LIKE '%_oauth') OR (access_token IS NOT NULL)"
    )
    op.create_check_constraint(
        'ck_auth_details_password_requires_hash',
        'auth_details',
        "(auth_type != 'password') OR (hashed_password IS NOT NULL)"
    )

    # Step 8: Add indexes
    op.create_index('idx_auth_details_auth_type', 'auth_details', ['auth_type'], unique=False)
    op.create_index('idx_auth_details_email_verification_token', 'auth_details', ['email_verification_token'], unique=False)
    op.create_index('idx_auth_details_password_reset_token', 'auth_details', ['password_reset_token'], unique=False)

    # Step 9: Update table comment
    op.create_table_comment(
        'auth_details',
        'Authentication details per user - supports OAuth and password',
        existing_comment='OAuth tokens per platform - encrypted at application level',
        schema=None
    )


def downgrade() -> None:
    """Revert auth_details table to original OAuth-only structure."""

    # Step 1: Revert table comment
    op.create_table_comment(
        'auth_details',
        'OAuth tokens per platform - encrypted at application level',
        existing_comment='Authentication details per user - supports OAuth and password',
        schema=None
    )

    # Step 2: Drop indexes (with IF EXISTS for safety)
    op.execute('DROP INDEX IF EXISTS idx_auth_details_password_reset_token')
    op.execute('DROP INDEX IF EXISTS idx_auth_details_email_verification_token')
    op.execute('DROP INDEX IF EXISTS idx_auth_details_auth_type')

    # Step 3: Drop check constraints (with IF EXISTS for safety)
    op.execute('ALTER TABLE auth_details DROP CONSTRAINT IF EXISTS ck_auth_details_password_requires_hash')
    op.execute('ALTER TABLE auth_details DROP CONSTRAINT IF EXISTS ck_auth_details_oauth_requires_token')
    op.execute('ALTER TABLE auth_details DROP CONSTRAINT IF EXISTS ck_auth_details_valid_auth_type')

    # Step 4: Drop unique constraint and restore old one (with IF EXISTS for safety)
    op.execute('ALTER TABLE auth_details DROP CONSTRAINT IF EXISTS uq_auth_details_user_auth_type')
    op.create_unique_constraint('uq_auth_details_user_platform', 'auth_details', ['user_id', 'platform'])

    # Step 5: Restore old platform check constraint
    op.create_check_constraint(
        'ck_auth_details_valid_platform',
        'auth_details',
        "platform IN ('google', 'linkedin', 'github', 'twitter')"
    )

    # Step 6: Delete password-only records before making OAuth fields NOT NULL
    # (password records have platform=NULL which would violate NOT NULL constraint)
    op.execute("""
        DELETE FROM auth_details
        WHERE auth_type = 'password'
    """)

    # Step 6b: Make OAuth fields NOT NULL again
    op.alter_column('auth_details', 'token_expiry', existing_type=postgresql.TIMESTAMP(timezone=True), nullable=False)
    op.alter_column('auth_details', 'access_token', existing_type=sa.TEXT(), nullable=False)
    op.alter_column('auth_details', 'avatar', existing_type=sa.TEXT(), nullable=False)
    op.alter_column('auth_details', 'platform_username', existing_type=sa.TEXT(), nullable=False)
    op.alter_column('auth_details', 'platform_user_id', existing_type=sa.TEXT(), nullable=False)
    op.alter_column('auth_details', 'platform', existing_type=sa.TEXT(), nullable=False)

    # Step 7: Drop password-specific fields (with IF EXISTS for safety)
    op.execute('ALTER TABLE auth_details DROP COLUMN IF EXISTS email_verified_at')
    op.execute('ALTER TABLE auth_details DROP COLUMN IF EXISTS last_password_change')
    op.execute('ALTER TABLE auth_details DROP COLUMN IF EXISTS locked_until')
    op.execute('ALTER TABLE auth_details DROP COLUMN IF EXISTS failed_login_attempts')
    op.execute('ALTER TABLE auth_details DROP COLUMN IF EXISTS password_reset_expires')
    op.execute('ALTER TABLE auth_details DROP COLUMN IF EXISTS password_reset_token')
    op.execute('ALTER TABLE auth_details DROP COLUMN IF EXISTS email_verification_token_expires')
    op.execute('ALTER TABLE auth_details DROP COLUMN IF EXISTS email_verification_token')
    op.execute('ALTER TABLE auth_details DROP COLUMN IF EXISTS hashed_password')

    # Step 8: Drop auth_type column (with IF EXISTS for safety)
    op.execute('ALTER TABLE auth_details DROP COLUMN IF EXISTS auth_type')
