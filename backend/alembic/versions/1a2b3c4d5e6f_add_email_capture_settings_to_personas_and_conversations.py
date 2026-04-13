"""Add email capture settings to personas and conversations

Revision ID: 1a2b3c4d5e6f
Revises: 0e763f7538c0
Create Date: 2025-11-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, Sequence[str], None] = '0e763f7538c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add email capture settings to personas and user info to conversations."""

    # Add email capture settings to personas table
    op.add_column('personas', sa.Column('email_capture_enabled', sa.Boolean(), server_default='false', nullable=False, comment='Whether to prompt visitors for email'))
    op.add_column('personas', sa.Column('email_capture_message_threshold', sa.Integer(), server_default='5', nullable=False, comment='Number of messages before prompting for email (default: 5)'))
    op.add_column('personas', sa.Column('email_capture_require_fullname', sa.Boolean(), server_default='true', nullable=False, comment='Whether full name is required when capturing email'))
    op.add_column('personas', sa.Column('email_capture_require_phone', sa.Boolean(), server_default='false', nullable=False, comment='Whether phone number is required when capturing email'))

    # Add user fullname and phone to conversations table
    op.add_column('conversations', sa.Column('user_fullname', sa.String(length=255), nullable=True, comment="User's full name (captured during email collection)"))
    op.add_column('conversations', sa.Column('user_phone', sa.String(length=50), nullable=True, comment="User's phone number (optional during email collection)"))


def downgrade() -> None:
    """Downgrade schema - remove email capture settings from personas and user info from conversations."""

    # Remove user info from conversations table
    op.drop_column('conversations', 'user_phone')
    op.drop_column('conversations', 'user_fullname')

    # Remove email capture settings from personas table
    op.drop_column('personas', 'email_capture_require_phone')
    op.drop_column('personas', 'email_capture_require_fullname')
    op.drop_column('personas', 'email_capture_message_threshold')
    op.drop_column('personas', 'email_capture_enabled')
