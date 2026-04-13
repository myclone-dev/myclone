"""add_persona_access_otps_table

Revision ID: ff75d8a68c38
Revises: 87873e4ce88c
Create Date: 2025-10-30 01:41:25.392847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'ff75d8a68c38'
down_revision: Union[str, Sequence[str], None] = '87873e4ce88c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create persona_access_otps table for OTP verification
    op.create_table(
        'persona_access_otps',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('persona_id', UUID(as_uuid=True), sa.ForeignKey('personas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('otp_code', sa.String(6), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_attempts', sa.Integer(), server_default='3', nullable=False),
        sa.CheckConstraint('attempts <= max_attempts', name='ck_persona_access_otps_max_attempts'),
    )

    # Create indexes
    op.create_index('idx_persona_access_otps_lookup', 'persona_access_otps', ['persona_id', 'email', 'otp_code'])
    op.create_index('idx_persona_access_otps_expires', 'persona_access_otps', ['expires_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_persona_access_otps_expires', table_name='persona_access_otps')
    op.drop_index('idx_persona_access_otps_lookup', table_name='persona_access_otps')

    # Drop table
    op.drop_table('persona_access_otps')
