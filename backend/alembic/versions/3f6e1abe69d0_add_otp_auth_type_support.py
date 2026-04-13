"""add_otp_auth_type_support

Revision ID: 3f6e1abe69d0
Revises: cecbbd8a90eb
Create Date: 2025-12-11 21:57:13.016202

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f6e1abe69d0'
down_revision: Union[str, Sequence[str], None] = 'cecbbd8a90eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add OTP auth type support for VISITOR users with passwordless authentication.

    Changes:
    1. Add 'otp' to valid auth_type values
    2. Add constraint: OTP auth type cannot have hashed_password

    Auth types after this migration:
    - 'linkedin_oauth': Login via LinkedIn OAuth
    - 'google_oauth': Login via Google OAuth
    - 'password': Login via email + password (CREATOR accounts)
    - 'otp': Login via email + OTP code (VISITOR accounts)
    """
    # Drop existing auth_type constraint
    op.drop_constraint('ck_auth_details_valid_auth_type', 'auth_details', type_='check')

    # Recreate with 'otp' added
    op.create_check_constraint(
        'ck_auth_details_valid_auth_type',
        'auth_details',
        "auth_type IN ('linkedin_oauth', 'google_oauth', 'password', 'otp')"
    )

    # Add constraint: OTP auth type must NOT have hashed_password
    op.create_check_constraint(
        'ck_auth_details_otp_no_password',
        'auth_details',
        "(auth_type != 'otp') OR (hashed_password IS NULL)"
    )


def downgrade() -> None:
    """
    Revert OTP auth type support.

    WARNING: This will fail if any auth_details records exist with auth_type='otp'.
    You must manually delete or migrate those records before downgrading.
    """
    # Drop OTP-specific constraint
    op.drop_constraint('ck_auth_details_otp_no_password', 'auth_details', type_='check')

    # Drop current auth_type constraint
    op.drop_constraint('ck_auth_details_valid_auth_type', 'auth_details', type_='check')

    # Recreate without 'otp'
    op.create_check_constraint(
        'ck_auth_details_valid_auth_type',
        'auth_details',
        "auth_type IN ('linkedin_oauth', 'google_oauth', 'password')"
    )
