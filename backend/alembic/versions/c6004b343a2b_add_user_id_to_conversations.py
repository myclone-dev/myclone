"""add_user_id_to_conversations

Revision ID: c6004b343a2b
Revises: 3f6e1abe69d0
Create Date: 2025-12-12 11:52:31.721764

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'c6004b343a2b'
down_revision: Union[str, Sequence[str], None] = '3f6e1abe69d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add user_id column to conversations table for authenticated user linking.

    Changes:
    1. Add nullable user_id column (UUID) to conversations table
    2. Backfill user_id for existing conversations where user_email matches users.email
    3. Add foreign key constraint to users table (SET NULL on delete)
    4. Add index on user_id for query performance

    Use cases:
    - user_id = NULL: Anonymous conversations (no account)
    - user_id = UUID: Authenticated user conversations (permanent link)
    - user_email still used as fallback for non-registered users

    Data Migration:
    Backfills user_id for existing conversations where:
    - user_email matches an existing user's email
    - Excludes anonymous emails (anon_*@session.local)
    This prevents fragmented conversation history when users authenticate later.
    """
    # Step 1: Add user_id column (nullable to support anonymous conversations)
    op.add_column(
        'conversations',
        sa.Column(
            'user_id',
            UUID(as_uuid=True),
            nullable=True,
            comment='Foreign key to users table - NULL for anonymous conversations, UUID for authenticated users'
        )
    )

    # Step 2: Backfill user_id for existing conversations where user_email matches users.email
    # This prevents fragmented history when users authenticate after providing email
    op.execute("""
        UPDATE conversations c
        SET user_id = u.id
        FROM users u
        WHERE c.user_email = u.email
          AND c.user_id IS NULL
          AND c.user_email IS NOT NULL
          AND c.user_email NOT LIKE 'anon_%@session.local'
    """)

    # Step 3: Add foreign key constraint (SET NULL on user deletion to preserve conversation history)
    op.create_foreign_key(
        'fk_conversations_user_id',
        'conversations',
        'users',
        ['user_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Step 4: Add index for efficient user-based queries
    op.create_index(
        'ix_conversations_user_id',
        'conversations',
        ['user_id']
    )


def downgrade() -> None:
    """
    Remove user_id column and related constraints from conversations table.

    WARNING: This will remove the permanent link between conversations and users.
    Conversations will fall back to email-based identification only.
    """
    # Drop index
    op.drop_index('ix_conversations_user_id', table_name='conversations')

    # Drop foreign key constraint
    op.drop_constraint('fk_conversations_user_id', 'conversations', type_='foreignkey')

    # Drop user_id column
    op.drop_column('conversations', 'user_id')
