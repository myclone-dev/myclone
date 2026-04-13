"""add_checksum_to_documents

Revision ID: a1f2b3c4d5e6
Revises: dc173165fc29
Create Date: 2025-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'dc173165fc29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add checksum column to documents table for duplicate detection.
    
    The checksum is stored as a generated column that extracts the 'checksum' 
    value from the metadata JSONB field. This allows for efficient duplicate 
    detection without adding a new physical column.

    Important behavioral notes:
    - Checksum can be NULL (for documents uploaded before this feature)
    - Uniqueness is determined by the combination of (user_id, checksum)
    - Multiple users can upload the same file (same checksum) from different accounts
    - Duplicate detection only applies within a single user's documents
    """
    
    # Add checksum as a generated column from metadata->>'checksum'
    # Note: The column name in PostgreSQL is 'metadata', not 'metadata_'
    # The column is nullable by default - existing documents will have NULL checksum
    op.execute("""
        ALTER TABLE documents 
        ADD COLUMN checksum TEXT 
        GENERATED ALWAYS AS (metadata->>'checksum') STORED
    """)
    
    # Add column comment explaining the behavior
    op.execute("""
        COMMENT ON COLUMN documents.checksum IS 
        'SHA-256 checksum of file content for duplicate detection. NULL for documents without checksum in metadata. Duplicate detection is per-user (user_id + checksum combination).'
    """)

    # Create a composite index on (user_id, checksum) for efficient per-user duplicate detection
    # This allows multiple users to have the same file (same checksum)
    # The partial index only includes rows where checksum IS NOT NULL
    op.create_index(
        'idx_documents_checksum_user',
        'documents',
        ['user_id', 'checksum'],
        unique=False,  # Not globally unique - same file can exist for different users
        postgresql_where=sa.text("checksum IS NOT NULL")
    )


def downgrade() -> None:
    """Remove checksum column and index"""
    
    # Drop the index first
    op.drop_index('idx_documents_checksum_user', table_name='documents')
    
    # Drop the checksum column
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS checksum")
