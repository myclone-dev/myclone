"""add_trigger_for_llamalite_embeddings_custom_columns

Revision ID: d7660f64a64b
Revises: 13b9596d4900
Create Date: 2025-12-03 17:39:44.398485

Add database trigger to automatically populate custom columns from metadata_ JSONB
for data_llamalite_embeddings table. This mirrors the trigger for data_llamaindex_embeddings.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7660f64a64b'
down_revision: Union[str, Sequence[str], None] = '13b9596d4900'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trigger to auto-populate custom columns from metadata JSONB for llamalite embeddings."""


    # Step 1: Create trigger function to populate columns from metadata_ JSONB
    print("Creating trigger function for llamalite embeddings...")
    op.execute("""
        CREATE OR REPLACE FUNCTION populate_embedding_lite_custom_columns()
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
    print("Creating trigger for llamalite embeddings...")
    op.execute("""
        CREATE TRIGGER trigger_populate_embedding_lite_columns
        BEFORE INSERT ON data_llamalite_embeddings
        FOR EACH ROW
        EXECUTE FUNCTION populate_embedding_lite_custom_columns();
    """)

    print("✅ Trigger created successfully - custom columns will auto-populate from metadata_ for data_llamalite_embeddings")


def downgrade() -> None:
    """Remove trigger and restore NOT NULL constraints."""

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trigger_populate_embedding_lite_columns ON data_llamalite_embeddings")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS populate_embedding_lite_custom_columns()")
