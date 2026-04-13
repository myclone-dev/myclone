"""add_claim_code_columns_to_users

Revision ID: dda04d5cd0d5
Revises: abc123def456
Create Date: 2025-11-18 11:12:04.508112

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dda04d5cd0d5'
down_revision: Union[str, Sequence[str], None] = 'abc123def456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add claim code columns to users table for account claiming flow."""
    # Add claim code columns to users table
    op.add_column('users', sa.Column('claim_code', sa.String(64), nullable=True))
    op.add_column('users', sa.Column('claim_code_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('claim_code_attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('claim_code_generated_at', sa.DateTime(timezone=True), nullable=True))

    # Create unique constraint on claim_code
    op.create_unique_constraint('uq_users_claim_code', 'users', ['claim_code'])

    # Create index for fast claim code lookup (only for active codes)
    op.execute("""
        CREATE INDEX idx_users_claim_code_active
        ON users(claim_code)
        WHERE claim_code IS NOT NULL
    """)


def downgrade() -> None:
    """Remove claim code columns from users table."""
    # Drop index
    op.drop_index('idx_users_claim_code_active', table_name='users')

    # Drop unique constraint
    op.drop_constraint('uq_users_claim_code', 'users', type_='unique')

    # Drop columns
    op.drop_column('users', 'claim_code_generated_at')
    op.drop_column('users', 'claim_code_attempts')
    op.drop_column('users', 'claim_code_expires_at')
    op.drop_column('users', 'claim_code')
