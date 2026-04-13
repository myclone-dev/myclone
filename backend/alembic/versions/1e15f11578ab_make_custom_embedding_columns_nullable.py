"""make_custom_embedding_columns_nullable

Revision ID: 1e15f11578ab
Revises: 658aed2d84a4
Create Date: 2025-10-13 21:05:52.345527

Add database trigger to automatically populate custom columns from metadata_ JSONB.
This eliminates the need for post-insert UPDATE queries.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e15f11578ab'
down_revision: Union[str, Sequence[str], None] = '658aed2d84a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trigger to auto-populate custom columns from metadata JSONB."""

    # Step 1: Make custom columns nullable (allows old data and staged inserts)
    print("Making custom columns nullable...")
    op.alter_column('data_llamaindex_embeddings', 'user_id', nullable=True)
    op.alter_column('data_llamaindex_embeddings', 'source_record_id', nullable=True)
    op.alter_column('data_llamaindex_embeddings', 'source', nullable=True)
    op.alter_column('data_llamaindex_embeddings', 'source_type', nullable=True)

    # Step 2: Create trigger function to populate columns from metadata_ JSONB
    print("Creating trigger function...")
    op.execute("""
        CREATE OR REPLACE FUNCTION populate_embedding_custom_columns()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Only populate if values are NULL (allows manual override)
            IF NEW.user_id IS NULL AND NEW.metadata_ ? 'user_id' THEN
                NEW.user_id = (NEW.metadata_->>'user_id')::uuid;
            END IF;

            IF NEW.source_record_id IS NULL AND NEW.metadata_ ? 'source_record_id' THEN
                NEW.source_record_id = (NEW.metadata_->>'source_record_id')::uuid;
            END IF;

            IF NEW.source IS NULL AND NEW.metadata_ ? 'source' THEN
                NEW.source = NEW.metadata_->>'source';
            END IF;

            IF NEW.source_type IS NULL AND NEW.metadata_ ? 'source_type' THEN
                NEW.source_type = NEW.metadata_->>'source_type';
            END IF;

            -- posted_at is optional, only set if present in metadata
            IF NEW.posted_at IS NULL AND NEW.metadata_ ? 'posted_at' THEN
                BEGIN
                    NEW.posted_at = (NEW.metadata_->>'posted_at')::timestamptz;
                EXCEPTION WHEN OTHERS THEN
                    -- If conversion fails, leave as NULL
                    NULL;
                END;
            END IF;

            -- created_at defaults to now if not set
            IF NEW.created_at IS NULL THEN
                NEW.created_at = NOW();
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Step 3: Create BEFORE INSERT trigger
    print("Creating trigger...")
    op.execute("""
        CREATE TRIGGER trigger_populate_embedding_columns
        BEFORE INSERT ON data_llamaindex_embeddings
        FOR EACH ROW
        EXECUTE FUNCTION populate_embedding_custom_columns();
    """)

    print("✅ Trigger created successfully - custom columns will auto-populate from metadata_")


def downgrade() -> None:
    """Remove trigger and restore NOT NULL constraints."""

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trigger_populate_embedding_columns ON data_llamaindex_embeddings")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS populate_embedding_custom_columns()")

    # Restore NOT NULL constraints (only if all rows have values)
    # Note: This may fail if there are NULL values - manual cleanup required
    print("Restoring NOT NULL constraints...")
    op.alter_column('data_llamaindex_embeddings', 'user_id', nullable=False)
    op.alter_column('data_llamaindex_embeddings', 'source_record_id', nullable=False)
    op.alter_column('data_llamaindex_embeddings', 'source', nullable=False)
    op.alter_column('data_llamaindex_embeddings', 'source_type', nullable=False)
